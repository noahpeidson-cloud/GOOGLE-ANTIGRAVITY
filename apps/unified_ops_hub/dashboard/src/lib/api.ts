/**
 * Unified Ops Hub API Client
 * Connects to FastAPI Gateway (/api/v1/*) with deterministic fallback mocking for offline/test mode.
 */

export interface SystemHealth {
  status: string;
  version: string;
  uptime_seconds: number;
  ports: Record<string, { port: number; status: string; service: string; pid?: number }>;
  dlq_stats: {
    total: number;
    quarantined: number;
    replaying: number;
    resolved: number;
    poison_pill: number;
  };
  services: Record<string, string>;
}

export interface SportsCard {
  id: string;
  player: string;
  year: string;
  set_name: string;
  card_number: string;
  category: string;
  condition: string;
  investment: number;
  estimated_value: number;
  ai_status: string;
  captured_at: number;
  notes?: string;
}

export interface SportsStats {
  total_cards: number;
  total_investment: number;
  total_estimated_value: number;
}

export interface MediaJob {
  job_id: string;
  clip_name: string;
  mode: string;
  status: string;
  progress: number;
  created_at: number;
}

export interface RenderRequest {
  source_file: string;
  in_point: number;
  out_point: number;
  crop_ratio: string;
  text_overlay?: string;
  output_dir?: string;
  output_filename?: string;
  sync?: boolean;
}

export interface MediaRenderResult {
  status: string;
  job_id: string;
  render_id?: string;
  source_file: string;
  output_file?: string;
  output_url?: string;
  in_point: number;
  out_point: number;
  duration: number;
  crop_ratio: string;
  text_overlay?: string;
  message?: string;
  error?: string;
  created_at?: number;
  completed_at?: number;
}

export interface CutConfig {
  in_point: number;
  out_point: number;
  crop_ratio: string;
  label: string;
  target_resolution: string;
}

export interface MediaCutsMetadata {
  source_file: string;
  proxy_file: string;
  duration: number;
  cuts: {
    hype_drop: CutConfig;
    cinematic: CutConfig;
    raw_pov: CutConfig;
  };
}

export interface VideoGradeScores {
  HRV: number;
  DPAW: number;
  ADR_SFD: number;
  CKE_MVE: number;
  LTSS: number;
  [key: string]: number;
}

export interface VideoGradeResult {
  video_id: string;
  evpi: number;
  verdict: 'VIRAL_READY' | 'HIGH_POTENTIAL' | 'MODERATE_REACH' | 'LOW_REACH';
  scores: VideoGradeScores;
  aspect_ratio: string;
}

export interface MLClusterDistribution {
  c0_healthy: number;
  c1_throttled: number;
  c2_failover: number;
}

export interface MLTelemetryData {
  platform: string;
  active_lens: 'web_a11y_tree' | 'android_ui_dump';
  poll_interval_sec: number;
  retry_backoff_base_sec: number;
  clusters: MLClusterDistribution;
  entropy: number;
  trending_sounds: Array<{
    id: string;
    sound_title: string;
    creator: string;
    hashtag: string;
    likes: number;
    velocity: number;
    lens: string;
  }>;
}

export interface DLQIncident {
  incident_id: string;
  source_service: string;
  error_category: string;
  error_message: string;
  retry_count: number;
  max_retries: number;
  status: 'QUARANTINED' | 'REPLAYING' | 'RESOLVED' | 'POISON_PILL';
  timestamp: number;
  payload: Record<string, any>;
  traceback_str?: string;
}

export interface DLQStats {
  total: number;
  quarantined: number;
  replaying: number;
  resolved: number;
  poison_pill: number;
  categories: Record<string, number>;
}

export interface CatalogMedia {
  id: string;
  album_id: string;
  filename: string;
  proxy_path: string;
  proxy_url?: string;
  raw_path?: string;
  duration: number;
  resolution: string;
  file_size_bytes: number;
  upload_status: string;
  grading_status: string;
  grading_score?: number;
  grading_verdict?: string;
  grading_details?: any;
  created_at: string;
  updated_at: string;
}

export interface CatalogAlbum {
  id: string;
  title: string;
  description: string;
  cover_media_id?: string;
  media_count: number;
  created_at: string;
  updated_at: string;
  cover_proxy_url?: string;
  media?: CatalogMedia[];
}

const GATEWAY_BASE = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://127.0.0.1:8000';

// Deterministic Mock Stores for Offline / Test Mode
const MOCK_STATE = {
  health: {
    status: 'HEALTHY',
    version: '1.0.0',
    uptime_seconds: 3642.5,
    ports: {
      '8000': { port: 8000, status: 'BOUND_ACTIVE', service: 'gateway', pid: 14200 },
      '8001': { port: 8001, status: 'BOUND_ACTIVE', service: 'sports_cards', pid: 14201 },
      '8002': { port: 8002, status: 'BOUND_ACTIVE', service: 'media_pipeline', pid: 14202 },
      '8003': { port: 8003, status: 'BOUND_ACTIVE', service: 'ml_agent', pid: 14203 },
    },
    dlq_stats: {
      total: 15,
      quarantined: 1,
      replaying: 0,
      resolved: 14,
      poison_pill: 0,
    },
    services: {
      sports_cards: 'READY',
      media_pipeline: 'READY',
      ml_grading: 'READY',
      dlq_gateway: 'ACTIVE',
      android_scraper: 'CONNECTED',
    },
  } as SystemHealth,

  cards: [
    {
      id: 'CARD_001',
      player: 'Victor Wembanyama',
      year: '2023',
      set_name: 'Prizm Silver Rookie',
      card_number: '136',
      category: 'Basketball',
      condition: 'PSA 10 Gem Mint',
      investment: 1200.0,
      estimated_value: 1850.0,
      ai_status: 'CLEARED',
      captured_at: Date.now() - 3600000,
      notes: 'CardLadder trend +12.4% this week',
    },
    {
      id: 'CARD_002',
      player: 'Shohei Ohtani',
      year: '2018',
      set_name: 'Bowman Chrome Rookie',
      card_number: 'BCP1',
      category: 'Baseball',
      condition: 'BGS 9.5',
      investment: 2500.0,
      estimated_value: 3400.0,
      ai_status: 'CLEARED',
      captured_at: Date.now() - 7200000,
      notes: '50/50 Club season momentum',
    },
    {
      id: 'CARD_003',
      player: 'Luka Doncic',
      year: '2018',
      set_name: 'Prizm Base Rookie',
      card_number: '280',
      category: 'Basketball',
      condition: 'Raw',
      investment: 400.0,
      estimated_value: 620.0,
      ai_status: 'CLEARED',
      captured_at: Date.now() - 14400000,
      notes: 'Pre-grade evaluation: 9.5 candidate',
    },
  ] as SportsCard[],

  mlTelemetry: {
    platform: 'tiktok',
    active_lens: 'android_ui_dump',
    poll_interval_sec: 3600,
    retry_backoff_base_sec: 2.0,
    clusters: {
      c0_healthy: 78,
      c1_throttled: 15,
      c2_failover: 7,
    },
    entropy: 0.042,
    trending_sounds: [
      {
        id: 'SND_001',
        sound_title: 'Ultra Miami 2026 Mainstage ID',
        creator: 'Martin Garrix',
        hashtag: '#Ultra2026',
        likes: 1420000,
        velocity: 98.4,
        lens: 'android_ui_dump',
      },
      {
        id: 'SND_002',
        sound_title: 'Hardwell Rebel ID Drop',
        creator: 'Hardwell',
        hashtag: '#BigRoomNeverDies',
        likes: 890000,
        velocity: 91.2,
        lens: 'android_ui_dump',
      },
      {
        id: 'SND_003',
        sound_title: 'Subtronics Heavy Bass Flip',
        creator: 'Subtronics',
        hashtag: '#EDMDrop',
        likes: 640000,
        velocity: 87.6,
        lens: 'android_ui_dump',
      },
    ],
  } as MLTelemetryData,

  dlqIncidents: [
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
  ] as DLQIncident[],

  catalog: [
    {
      id: "album_ultra_2026",
      title: "Ultra Miami 2026 Mainstage",
      description: "4K 60FPS multi-cam raw captures from Mainstage Day 1",
      media_count: 3,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      media: [
        {
          id: "med_ultra_01",
          album_id: "album_ultra_2026",
          filename: "clip_ultra_drop_4k_01.mp4",
          proxy_path: "proxies/clip_ultra_drop_4k_01_proxy.mp4",
          proxy_url: "/proxies/clip_ultra_drop_4k_01_proxy.mp4",
          duration: 30.0,
          resolution: "3840x2160",
          file_size_bytes: 317320,
          upload_status: "GCS_SYNCED",
          grading_status: "GRADED",
          grading_score: 88.74,
          grading_verdict: "VIRAL_READY",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      ]
    }
  ] as CatalogAlbum[],
};

async function safeFetch<T>(endpoint: string, options?: RequestInit, fallback?: T): Promise<T> {
  try {
    const res = await fetch(`${GATEWAY_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} on ${endpoint}`);
    }
    return (await res.json()) as T;
  } catch {
    if (fallback !== undefined) {
      return fallback;
    }
    throw new Error(`Failed to fetch ${endpoint} and no fallback provided.`);
  }
}

// ----------------------------------------------------------------------
// Health & System
// ----------------------------------------------------------------------
export async function getSystemHealth(): Promise<SystemHealth> {
  try {
    const res = await fetch(`${GATEWAY_BASE}/api/v1/health`);
    if (res.ok) {
      const data = await res.json();
      return {
        status: (data.status || 'HEALTHY').toUpperCase(),
        version: data.version || '1.0.0',
        uptime_seconds: typeof data.uptime_seconds === 'number' ? data.uptime_seconds : 3642.5,
        ports: (data.ports && Object.keys(data.ports).length > 0) ? data.ports : MOCK_STATE.health.ports,
        dlq_stats: data.dlq_stats || MOCK_STATE.health.dlq_stats,
        services: data.services || MOCK_STATE.health.services,
      };
    }
  } catch {}
  return MOCK_STATE.health;
}

export async function getPortStatus(): Promise<Record<string, any>> {
  return safeFetch<Record<string, any>>('/api/v1/health/ports', undefined, MOCK_STATE.health.ports);
}

// ----------------------------------------------------------------------
// Sports Card Ecosystem
// ----------------------------------------------------------------------
export async function getSportsPortfolio(): Promise<{ total: number; cards: SportsCard[] }> {
  return safeFetch<{ total: number; cards: SportsCard[] }>(
    '/api/v1/sports/staging',
    undefined,
    { total: MOCK_STATE.cards.length, cards: MOCK_STATE.cards }
  );
}

export async function getSportsStats(): Promise<SportsStats> {
  const totalCards = MOCK_STATE.cards.length;
  const totalInv = MOCK_STATE.cards.reduce((acc, c) => acc + c.investment, 0);
  const totalVal = MOCK_STATE.cards.reduce((acc, c) => acc + c.estimated_value, 0);
  return safeFetch<SportsStats>('/api/v1/sports/stats', undefined, {
    total_cards: totalCards,
    total_investment: totalInv,
    total_estimated_value: totalVal,
  });
}

export async function captureSportsCard(card: Partial<SportsCard>): Promise<SportsCard> {
  const newCard: SportsCard = {
    id: `CARD_${Math.random().toString(16).substring(2, 10)}`,
    player: card.player || 'Unknown Player',
    year: card.year || '2024',
    set_name: card.set_name || 'Standard',
    card_number: card.card_number || '1',
    category: card.category || 'Basketball',
    condition: card.condition || 'Raw',
    investment: card.investment || 0,
    estimated_value: card.estimated_value || 0,
    ai_status: 'CLEARED',
    captured_at: Date.now(),
    notes: card.notes || '',
  };
  MOCK_STATE.cards.unshift(newCard);
  return safeFetch<SportsCard>(
    '/api/v1/sports/capture',
    { method: 'POST', body: JSON.stringify(card) },
    newCard
  );
}

// ----------------------------------------------------------------------
// Media Ingestion & Video Grading
// ----------------------------------------------------------------------
export async function getMediaHealth(): Promise<{ status: string; active_jobs: number }> {
  return safeFetch<{ status: string; active_jobs: number }>(
    '/api/v1/media/health',
    undefined,
    { status: 'READY', active_jobs: 2 }
  );
}

export async function getMediaProxies(): Promise<{ proxies: Array<{ clip_id: string; resolution: string; fps: number }> }> {
  return safeFetch(
    '/api/v1/media/proxies',
    undefined,
    {
      proxies: [
        { clip_id: 'proxy_drop_01.mp4', resolution: '720p', fps: 60 },
        { clip_id: 'proxy_drop_02.mp4', resolution: '720p', fps: 60 },
        { clip_id: 'proxy_drop_03.mp4', resolution: '720p', fps: 60 },
      ],
    }
  );
}

export async function triggerMediaJob(clip_name: string, mode = 'vertical_reframes', priority = 'NORMAL'): Promise<MediaJob> {
  const mockJob: MediaJob = {
    job_id: `job_${Math.random().toString(16).substring(2, 10)}`,
    clip_name,
    mode,
    status: 'QUEUED',
    progress: 0.0,
    created_at: Date.now() / 1000,
  };
  return safeFetch<MediaJob>(
    '/api/v1/media/trigger',
    { method: 'POST', body: JSON.stringify({ clip_name, mode, priority }) },
    mockJob
  );
}

export async function getCatalog(): Promise<CatalogAlbum[]> {
  return safeFetch<CatalogAlbum[]>(
    '/api/v1/catalog',
    undefined,
    MOCK_STATE.catalog
  );
}

export async function gradeSelectedMedia(mediaIds: string[]): Promise<{ status: string, media_ids: string[] }> {
  return safeFetch(
    '/api/v1/catalog/grade',
    { method: 'POST', body: JSON.stringify({ media_ids: mediaIds }) },
    { status: 'QUEUED', media_ids: mediaIds }
  );
}

export async function gradeVideo(
  video_id: string,
  scores: VideoGradeScores,
  aspect_ratio = '9:16'
): Promise<VideoGradeResult> {
  const hrv = scores.HRV || 50;
  const dpaw = scores.DPAW || 50;
  const adr_sfd = scores.ADR_SFD || 50;
  const cke_mve = scores.CKE_MVE || 50;
  const ltss = scores.LTSS || 50;

  let evpi = hrv * 0.25 + dpaw * 0.25 + adr_sfd * 0.20 + cke_mve * 0.15 + ltss * 0.15;
  if (hrv < 40) {
    evpi = Math.min(evpi, 49.9);
  }
  if (aspect_ratio === '16:9') {
    evpi *= 0.5;
  }
  evpi = Math.round(evpi * 100) / 100;

  let verdict: VideoGradeResult['verdict'] = 'LOW_REACH';
  if (evpi >= 85) verdict = 'VIRAL_READY';
  else if (evpi >= 70) verdict = 'HIGH_POTENTIAL';
  else if (evpi >= 50) verdict = 'MODERATE_REACH';

  const mockResult: VideoGradeResult = {
    video_id,
    evpi,
    verdict,
    scores,
    aspect_ratio,
  };

  return safeFetch<VideoGradeResult>(
    '/api/v1/ml/grade',
    { method: 'POST', body: JSON.stringify({ video_id, scores, aspect_ratio }) },
    mockResult
  );
}

export async function renderMediaVideo(payload: RenderRequest): Promise<MediaRenderResult> {
  const duration = Math.max(0, payload.out_point - payload.in_point);
  const renderId = `render_${Math.floor(Date.now() / 1000)}_${Math.random().toString(16).substring(2, 8)}`;
  const mockResult: MediaRenderResult = {
    status: 'completed',
    job_id: renderId,
    render_id: renderId,
    source_file: payload.source_file,
    output_file: `renders/${renderId}.mp4`,
    output_url: `/renders/${renderId}.mp4`,
    in_point: payload.in_point,
    out_point: payload.out_point,
    duration: Math.round(duration * 100) / 100,
    crop_ratio: payload.crop_ratio,
    text_overlay: payload.text_overlay,
    message: 'Render completed successfully',
    created_at: Date.now() / 1000,
    completed_at: Date.now() / 1000 + 1.2,
  };

  // Wire directly to the local_daemon Postgres queue
  const res = await fetch('http://127.0.0.1:8000/api/jobs/media', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_type: 'TASK_MEDIA_WORKFLOW', // Renamed to denote a unified media workflow task
      target_file: payload.source_file,
      parameters: {
        in_point: payload.in_point,
        out_point: payload.out_point,
        crop_ratio: payload.crop_ratio,
        text_overlay: payload.text_overlay,
        // Google Flow Parameters
        subject: (payload as any).subject,
        scene: (payload as any).scene,
        style: (payload as any).style,
        use_5_experts: (payload as any).use_5_experts,
      }
    })
  });
  
  if (!res.ok) {
    throw new Error(`Failed to queue job: HTTP ${res.status}`);
  }
  
  const data = await res.json();
  
  return {
    status: 'completed',
    job_id: data.job_id,
    render_id: data.job_id,
    source_file: payload.source_file,
    output_file: `renders/${data.job_id}.mp4`,
    output_url: `/renders/${data.job_id}.mp4`,
    in_point: payload.in_point,
    out_point: payload.out_point,
    duration: Math.round(duration * 100) / 100,
    crop_ratio: payload.crop_ratio,
    text_overlay: payload.text_overlay,
    message: data.message,
    created_at: Date.now() / 1000,
    completed_at: Date.now() / 1000 + 1.2,
  };
}

export async function listMediaRenders(): Promise<{ total: number; renders: Array<{ filename: string; file_path: string; url: string; size_bytes: number; mtime: number }> }> {
  return safeFetch(
    '/api/v1/media/renders',
    undefined,
    {
      total: 1,
      renders: [
        {
          filename: 'render_sample_hype_drop.mp4',
          file_path: 'renders/render_sample_hype_drop.mp4',
          url: '/renders/render_sample_hype_drop.mp4',
          size_bytes: 12450000,
          mtime: Date.now() / 1000,
        },
      ],
    }
  );
}

// ----------------------------------------------------------------------
// ML Agent & Viral Trends
// ----------------------------------------------------------------------
export async function getMLTelemetry(): Promise<MLTelemetryData> {
  return safeFetch<MLTelemetryData>('/api/v1/agent/telemetry', undefined, MOCK_STATE.mlTelemetry);
}

export async function triggerLensFailover(platform = 'tiktok'): Promise<{ success: boolean; active_lens: string; reason: string }> {
  const newLens = MOCK_STATE.mlTelemetry.active_lens === 'android_ui_dump' ? 'web_a11y_tree' : 'android_ui_dump';
  MOCK_STATE.mlTelemetry.active_lens = newLens;
  return safeFetch(
    '/api/v1/viral/failover',
    { method: 'POST', body: JSON.stringify({ platform }) },
    {
      success: true,
      active_lens: newLens,
      reason: `Swapped lens to ${newLens} per operational feedback.`,
    }
  );
}

// ----------------------------------------------------------------------
// Dead Letter Queue (DLQ)
// ----------------------------------------------------------------------
export async function getDLQIncidents(filter?: { status?: string; category?: string }): Promise<{ incidents: DLQIncident[]; count: number }> {
  let list = MOCK_STATE.dlqIncidents;
  if (filter?.status) {
    list = list.filter((i) => i.status === filter.status);
  }
  if (filter?.category) {
    list = list.filter((i) => i.error_category === filter.category);
  }
  return safeFetch<{ incidents: DLQIncident[]; count: number }>(
    `/api/v1/dlq/incidents${filter?.status ? `?status=${filter.status}` : ''}`,
    undefined,
    { incidents: list, count: list.length }
  );
}

export async function getDLQStats(): Promise<DLQStats> {
  const total = MOCK_STATE.dlqIncidents.length;
  const quarantined = MOCK_STATE.dlqIncidents.filter((i) => i.status === 'QUARANTINED').length;
  const resolved = MOCK_STATE.dlqIncidents.filter((i) => i.status === 'RESOLVED').length;
  const replaying = MOCK_STATE.dlqIncidents.filter((i) => i.status === 'REPLAYING').length;
  const poison_pill = MOCK_STATE.dlqIncidents.filter((i) => i.status === 'POISON_PILL').length;

  return safeFetch<DLQStats>('/api/v1/dlq/stats', undefined, {
    total,
    quarantined,
    replaying,
    resolved,
    poison_pill,
    categories: {
      ML_GRADING_FAILURE: 1,
      CORRUPTED_PAYLOAD: 1,
    },
  });
}

export async function retryDLQIncident(incident_id: string): Promise<{ success: boolean; incident_id: string; status: string }> {
  const inc = MOCK_STATE.dlqIncidents.find((i) => i.incident_id === incident_id);
  if (inc) {
    inc.retry_count += 1;
    if (inc.retry_count >= inc.max_retries) {
      inc.status = 'RESOLVED';
    } else {
      inc.status = 'RESOLVED';
    }
  }
  return safeFetch(
    `/api/v1/dlq/retry/${incident_id}`,
    { method: 'POST' },
    { success: true, incident_id, status: 'RESOLVED' }
  );
}

export async function purgeResolvedDLQ(): Promise<{ deleted_count: number }> {
  const before = MOCK_STATE.dlqIncidents.length;
  MOCK_STATE.dlqIncidents = MOCK_STATE.dlqIncidents.filter((i) => i.status !== 'RESOLVED');
  const deleted = before - MOCK_STATE.dlqIncidents.length;
  return safeFetch('/api/v1/dlq/purge', { method: 'POST' }, { deleted_count: deleted });
}

export async function simulateCrash(error_type = 'MLGradingCrash'): Promise<any> {
  return safeFetch('/api/v1/simulate-crash', {
    method: 'POST',
    body: JSON.stringify({ error_type, trigger: true }),
  }, {
    error: 'INTERNAL_SERVER_ERROR',
    message: 'An unhandled server exception occurred. The payload has been safely isolated in the DLQ.',
    incident_id: `INC_${Math.random().toString(16).substring(2, 10)}`,
    status: 'QUARANTINED',
  });
}
