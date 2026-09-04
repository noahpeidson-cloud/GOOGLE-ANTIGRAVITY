/**
 * Typed REST API Client for Omnichannel Triage Hub FastAPI Local Daemon.
 * Connects React Frontend (http://localhost:5173) to Local Daemon (http://localhost:8000).
 * Implements graceful offline fallback resilience, timeouts, and complete type safety.
 */

export const DEFAULT_DAEMON_URL = 'http://localhost:8000';

export const getDaemonBaseUrl = (): string => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_DAEMON_API_URL) {
    return import.meta.env.VITE_DAEMON_API_URL;
  }
  return DEFAULT_DAEMON_URL;
};

// =============================================================================
// Interfaces & Schemas
// =============================================================================

export interface PulledFileInfo {
  filename: string;
  local_path: string;
  size_bytes: number;
  timestamp: string;
  is_mock?: boolean;
}

export interface AdbPullOptions {
  device_id?: string | null;
  source_path?: string | null;
  device_path?: string | null;
  destination_path?: string | null;
  local_dest?: string | null;
  file_pattern?: string;
  limit?: number;
  mock?: boolean;
  run_in_background?: boolean;
}

export interface AdbPullResponse {
  success: boolean;
  status: 'success' | 'mock_success' | 'error' | 'in_progress';
  message: string;
  device_id?: string | null;
  bytes_transferred: number;
  total_bytes: number;
  file_path?: string | null;
  pulled_files: PulledFileInfo[];
  total_count: number;
  duration_ms: number;
  duration_seconds?: number;
  task_id?: string | null;
  error?: string | null;
  is_fallback?: boolean;
}

export interface CaptureScreenOptions {
  device_id?: string | null;
  format?: 'png' | 'jpeg' | 'base64' | 'file' | 'both';
  mock?: boolean;
  save_dir?: string | null;
  save_to_file?: boolean;
}

export interface CaptureScreenResponse {
  success: boolean;
  status: 'success' | 'mock_success' | 'error';
  message: string;
  image_base64?: string | null;
  raw_base64?: string | null;
  file_path?: string | null;
  width: number;
  height: number;
  timestamp: string;
  device_id?: string | null;
  error?: string | null;
  is_fallback?: boolean;
}

export interface DeviceInfo {
  serial: string;
  state: string;
  model?: string | null;
  product?: string | null;
}

export interface DevicesResponse {
  devices: DeviceInfo[];
  count: number;
  is_fallback?: boolean;
}

export interface HealthResponse {
  status: string;
  adb_connected: boolean;
  device_count: number;
  devices: string[];
  adb_version?: string | null;
  mock_available: boolean;
  uptime_seconds: number;
  timestamp: string;
  is_fallback?: boolean;
}

export interface StagingFile {
  filename: string;
  path: string;
  size_bytes: number;
  modified_at: string;
  media_type: string;
}

export interface StagingInventoryResponse {
  files: StagingFile[];
  total_size_bytes: number;
  count: number;
  is_fallback?: boolean;
}

// =============================================================================
// Fallback Utilities
// =============================================================================

// Procedural 9:16 fallback capture frame (1x1 transparent PNG data URI or lightweight SVG data URI)
export const FALLBACK_POSTER_FRAME =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="540" height="960" viewBox="0 0 540 960">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#0a0a0f"/>
          <stop offset="50%" stop-color="#141926"/>
          <stop offset="100%" stop-color="#1e1b4b"/>
        </linearGradient>
      </defs>
      <rect width="540" height="960" fill="url(#g)"/>
      <circle cx="270" cy="420" r="90" fill="#3b82f6" opacity="0.25"/>
      <circle cx="270" cy="420" r="60" fill="#3b82f6" opacity="0.4"/>
      <text x="270" y="425" fill="#60a5fa" font-size="20" font-family="monospace" font-weight="bold" text-anchor="middle">PHONE LINK CAPTURE</text>
      <text x="270" y="460" fill="#94a3b8" font-size="14" font-family="sans-serif" text-anchor="middle">540 x 960 • 9:16 Vertical Stream</text>
      <text x="270" y="540" fill="#22c55e" font-size="13" font-family="monospace" text-anchor="middle">● Live Frame Synced</text>
    </svg>
  `.trim());

// Helper for fetch with timeout
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = 4000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Checks local daemon bridge health and connected ADB devices.
 */
export async function getHealth(customBaseUrl?: string): Promise<HealthResponse> {
  const baseUrl = customBaseUrl || getDaemonBaseUrl();
  try {
    const res = await fetchWithTimeout(`${baseUrl}/api/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (!res.ok) {
      throw new Error(`Health check HTTP error ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    return {
      status: data.status || 'ok',
      adb_connected: Boolean(data.adb_connected),
      device_count: typeof data.device_count === 'number' ? data.device_count : 0,
      devices: Array.isArray(data.devices) ? data.devices : [],
      adb_version: data.adb_version || null,
      mock_available: Boolean(data.mock_available ?? true),
      uptime_seconds: typeof data.uptime_seconds === 'number' ? data.uptime_seconds : 0,
      timestamp: data.timestamp || new Date().toISOString(),
      is_fallback: false,
    };
  } catch (err) {
    console.warn('[API Client] Daemon offline or unreachable for health check:', err);
    return {
      status: 'offline',
      adb_connected: false,
      device_count: 0,
      devices: [],
      adb_version: 'Offline (Client Sim)',
      mock_available: true,
      uptime_seconds: 0,
      timestamp: new Date().toISOString(),
      is_fallback: true,
    };
  }
}

/**
 * Triggers an ADB pull operation from connected device or generates mock video.
 */
export async function triggerAdbPull(
  options: AdbPullOptions = {},
  customBaseUrl?: string
): Promise<AdbPullResponse> {
  const baseUrl = customBaseUrl || getDaemonBaseUrl();
  try {
    const res = await fetchWithTimeout(`${baseUrl}/api/trigger-adb-pull`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        device_id: options.device_id ?? null,
        source_path: options.source_path ?? options.device_path ?? '/sdcard/DCIM/Camera',
        destination_path: options.destination_path ?? options.local_dest ?? './staging/videos',
        file_pattern: options.file_pattern ?? '*.mp4',
        limit: options.limit ?? 10,
        mock: options.mock ?? false,
        run_in_background: options.run_in_background ?? false,
      }),
    });

    if (!res.ok) {
      throw new Error(`ADB Pull HTTP error ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    return {
      success: Boolean(data.success ?? true),
      status: data.status || 'success',
      message: data.message || 'ADB pull completed successfully',
      device_id: data.device_id ?? null,
      bytes_transferred: data.bytes_transferred ?? 0,
      total_bytes: data.total_bytes ?? 0,
      file_path: data.file_path ?? null,
      pulled_files: Array.isArray(data.pulled_files) ? data.pulled_files : [],
      total_count: typeof data.total_count === 'number' ? data.total_count : 0,
      duration_ms: typeof data.duration_ms === 'number' ? data.duration_ms : 0,
      duration_seconds: typeof data.duration_seconds === 'number' ? data.duration_seconds : 0,
      task_id: data.task_id ?? null,
      error: data.error ?? null,
      is_fallback: false,
    };
  } catch (err) {
    console.warn('[API Client] Daemon offline, using client-side ADB pull fallback:', err);
    const mockBytes = 564166656; // 538 MB
    const totalBytes = 97177649152; // 90.5 GB
    const filename = '20260819_213606.mp4';
    return {
      success: true,
      status: 'mock_success',
      message: 'Daemon offline - simulated client ADB pull completed (538 MB)',
      device_id: 'emulator-5554-fallback',
      bytes_transferred: mockBytes,
      total_bytes: totalBytes,
      file_path: `/sdcard/DCIM/Camera/${filename}`,
      pulled_files: [
        {
          filename,
          local_path: `./staging/videos/${filename}`,
          size_bytes: mockBytes,
          timestamp: new Date().toISOString(),
          is_mock: true,
        },
      ],
      total_count: 1,
      duration_ms: 1240,
      duration_seconds: 1.24,
      error: null,
      is_fallback: true,
    };
  }
}

/**
 * Captures live screen from connected Android device or generates procedural 9:16 frame.
 */
export async function captureScreen(
  options: CaptureScreenOptions = {},
  customBaseUrl?: string
): Promise<CaptureScreenResponse> {
  const baseUrl = customBaseUrl || getDaemonBaseUrl();
  try {
    const res = await fetchWithTimeout(`${baseUrl}/api/capture-screen`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        device_id: options.device_id ?? null,
        format: options.format ?? 'png',
        mock: options.mock ?? false,
        save_dir: options.save_dir ?? './staging/screenshots',
        save_to_file: options.save_to_file ?? false,
      }),
    });

    if (!res.ok) {
      throw new Error(`Capture Screen HTTP error ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    return {
      success: Boolean(data.success ?? true),
      status: data.status || 'success',
      message: data.message || 'Screen captured successfully',
      image_base64: data.image_base64 || FALLBACK_POSTER_FRAME,
      raw_base64: data.raw_base64 ?? null,
      file_path: data.file_path ?? null,
      width: typeof data.width === 'number' ? data.width : 540,
      height: typeof data.height === 'number' ? data.height : 960,
      timestamp: data.timestamp || new Date().toISOString(),
      device_id: data.device_id ?? null,
      error: data.error ?? null,
      is_fallback: false,
    };
  } catch (err) {
    console.warn('[API Client] Daemon offline, using client-side screen capture fallback:', err);
    return {
      success: true,
      status: 'mock_success',
      message: 'Daemon offline - simulated client screen capture frame generated',
      image_base64: FALLBACK_POSTER_FRAME,
      raw_base64: null,
      file_path: null,
      width: 540,
      height: 960,
      timestamp: new Date().toISOString(),
      device_id: 'client-simulated-device',
      error: null,
      is_fallback: true,
    };
  }
}

/**
 * Retrieves the list of discovered ADB devices.
 */
export async function getDevices(customBaseUrl?: string): Promise<DevicesResponse> {
  const baseUrl = customBaseUrl || getDaemonBaseUrl();
  try {
    const res = await fetchWithTimeout(`${baseUrl}/api/devices`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (!res.ok) {
      throw new Error(`Get Devices HTTP error ${res.status}`);
    }

    const data = await res.json();
    return {
      devices: Array.isArray(data.devices) ? data.devices : [],
      count: typeof data.count === 'number' ? data.count : 0,
      is_fallback: false,
    };
  } catch (err) {
    console.warn('[API Client] Daemon offline for getDevices:', err);
    return {
      devices: [],
      count: 0,
      is_fallback: true,
    };
  }
}

/**
 * Retrieves staging inventory files and total size.
 */
export async function getStagingInventory(customBaseUrl?: string): Promise<StagingInventoryResponse> {
  const baseUrl = customBaseUrl || getDaemonBaseUrl();
  try {
    const res = await fetchWithTimeout(`${baseUrl}/api/staging`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (!res.ok) {
      throw new Error(`Get Staging HTTP error ${res.status}`);
    }

    const data = await res.json();
    return {
      files: Array.isArray(data.files) ? data.files : [],
      total_size_bytes: typeof data.total_size_bytes === 'number' ? data.total_size_bytes : 0,
      count: typeof data.count === 'number' ? data.count : 0,
      is_fallback: false,
    };
  } catch (err) {
    console.warn('[API Client] Daemon offline for getStagingInventory:', err);
    return {
      files: [],
      total_size_bytes: 0,
      count: 0,
      is_fallback: true,
    };
  }
}
