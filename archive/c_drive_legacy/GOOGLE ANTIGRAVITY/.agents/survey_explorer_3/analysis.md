# Survey Analysis Report: Frontend Dashboard Architecture & MediaStudio Web Editor

**Survey Explorer:** Survey Explorer 3 (Frontend Dashboard & Test Suite)  
**Date:** 2026-08-26  
**Target Project:** `unified_ops_hub/dashboard`  
**Authoritative Request Reference:** `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`

---

## 1. Executive Summary

This report delivers a deep technical survey of the `unified_ops_hub/dashboard` codebase and establishes the implementation blueprint for the Human-in-the-Loop **Media Studio Web Editor** (`MediaStudio.tsx`) and its accompanying deterministic test suite.

The dashboard is built on **Next.js 16.3.2 (App Router)** with **React 19.2.8**, **Tailwind CSS v4**, and **Vitest 3.0.5**. The existing test suite encompasses **13 test files and 72 tests**, all passing with 100% test reliability.

`MediaStudio.tsx` will provide a real-time, interactive video editing studio capable of:
1. Loading 720p H.264 proxies in an HTML5 video player with adaptive aspect ratio formatting (9:16 vertical vs 16:9 landscape vs raw).
2. Toggling 3 AI-generated base cuts (`hype_drop`, `cinematic`, `raw_pov`) that dynamically adjust trim boundaries and aspect ratios.
3. Providing dual-handle trim slider controls with millisecond-accurate in-point and out-point scrubbing.
4. Rendering Instagram-style text overlays with real-time DOM preview directly over the video player canvas.
5. Triggering headless 4K FFmpeg rendering via `POST /api/v1/media/render` with real-time status feedback and offline fallback resiliency.

---

## 2. Codebase Architecture Survey

### 2.1 Package & Dependency Matrix (`dashboard/package.json`)
```json
{
  "name": "unified-ops-hub-dashboard",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "lucide-react": "^1.16.0",
    "next": "^16.3.2",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "tailwind-merge": "^3.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.2.0",
    "@testing-library/user-event": "^14.6.1",
    "@types/node": "^20.17.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^26.0.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.3",
    "vitest": "^3.0.5"
  }
}
```

### 2.2 Framework & Directory Layout
```
unified_ops_hub/dashboard/
├── src/
│   ├── app/
│   │   ├── globals.css          # Tailwind CSS v4 @import, glass-panel styles
│   │   ├── layout.tsx           # Master HTML shell with dark mode styling
│   │   └── page.tsx             # CommandCenterDashboard with Tab switching
│   ├── components/
│   │   ├── DLQCenter.tsx        # Dead Letter Queue & Incident Isolation
│   │   ├── ErrorBoundary.tsx    # React Error Boundary for isolated subtrees
│   │   ├── LiveTelemetryStream.tsx # Real-time SSE telemetry feed
│   │   ├── MLAgentWidget.tsx    # PySpark K-Means & Trend lens optimizer
│   │   ├── MediaIngestionWidget.tsx # ADB Wi-Fi & EVPI 5-score grading
│   │   ├── SportsCardWidget.tsx # Card portfolio & market trends
│   │   └── SystemHealthHeader.tsx # Port, socket collision & service monitor
│   ├── lib/
│   │   └── api.ts               # Unified REST API client with mock fallbacks
│   └── setupTests.ts            # JSDOM mocks for matchMedia, ResizeObserver, EventSource
├── __tests__/                   # 13 Vitest test suites
├── vitest.config.ts             # Vitest test runner configuration
└── tsconfig.json                # TypeScript compiler config with @/ path aliases
```

### 2.3 State Management & Architectural Patterns
- **Local React State**: Standardized on React 19 client components (`'use client'`) using `useState`, `useRef`, `useCallback`, and `useEffect`.
- **API Client Layer (`src/lib/api.ts`)**: Implements `safeFetch<T>` with deterministic fallback mock stores. When the FastAPI gateway (`http://127.0.0.1:8000`) is offline or during automated test runs, API calls return structured mock data seamlessly.
- **Resilience Isolation**: Every major widget in `src/app/page.tsx` is wrapped in an `ErrorBoundary` to prevent single-component exceptions from crashing the parent DOM tree.
- **Styling Architecture**: Custom glassmorphism classes (`.glass-panel`, `.glass-panel-glow`) defined in `globals.css` with zinc-based dark theme (`zinc-950`, `zinc-900`, `zinc-800`), accent color coding per subsystem:
  - Sports Cards: Emerald (`emerald-400`, `emerald-950`)
  - Media & PySpark: Purple (`purple-400`, `purple-950`)
  - ML Agent: Cyan (`cyan-400`, `cyan-950`)
  - DLQ Center: Rose (`rose-400`, `rose-950`)
  - Media Studio (New): Fuchsia/Violet (`fuchsia-400`, `violet-500`, `fuchsia-950`)

### 2.4 Test Execution Baseline
- **Command**: `npm test` (`vitest run`)
- **Status**: 13/13 test files passing, 72/72 tests passing (execution duration: ~38s on Windows JSDOM environment).

---

## 3. Navigation & Views Integration for `MediaStudio.tsx`

### 3.1 Tab Navigation Extension (`dashboard/src/app/page.tsx`)
1. Extend `TabType`:
   ```tsx
   type TabType = 'overview' | 'sports' | 'media' | 'studio' | 'ml' | 'dlq';
   ```
2. Add Navigation Tab Button in `<nav aria-label="Dashboard views">`:
   ```tsx
   <button
     onClick={() => setActiveTab('studio')}
     className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
       activeTab === 'studio'
         ? 'bg-fuchsia-950/60 text-fuchsia-300 border border-fuchsia-700/50'
         : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
     }`}
   >
     <Scissors className="w-3.5 h-3.5 text-fuchsia-400" />
     Media Studio
   </button>
   ```
3. Add Dedicated View in `<main>`:
   ```tsx
   {activeTab === 'studio' && (
     <ErrorBoundary fallbackTitle="Media Studio Video Editor Error">
       <MediaStudio />
     </ErrorBoundary>
   )}
   ```
4. Co-location in the `media` tab:
   In addition to the dedicated `'studio'` tab, mounting `MediaStudio` inside `activeTab === 'media'` beneath or alongside `MediaIngestionWidget` allows operators to seamlessly grade ingested raw footage and then immediately edit it in the Media Studio.

---

## 4. `MediaStudio.tsx` Component Requirements & Specifications

### 4.1 HTML5 Video Player with 720p Proxy Support
- **Player Element**: Native `<video>` element with `controls`, `playsInline`, and custom time synchronization.
- **Proxy Loading**: Default source `/proxies/proxy_drop_01.mp4` with support for dynamic proxy selection from `getMediaProxies()`.
- **Dynamic Viewport Styling**:
  - `9:16`: `aspect-[9/16] max-w-[320px] mx-auto rounded-xl shadow-2xl`
  - `16:9`: `aspect-video max-w-2xl mx-auto rounded-xl shadow-2xl`
  - `original`: `max-w-2xl mx-auto rounded-xl shadow-2xl`

### 4.2 AI Base Cut Presets (3 Buttons)
Interactive toggle cards representing AI cut algorithms:
| Preset Key | Display Name | Crop Ratio | Default Trim Window | Description | Badge |
|---|---|---|---|---|---|
| `hype_drop` | **Hype Drop** | `9:16` | 05.00s – 15.00s (10s) | Trimmed to peak audio energy & cropped for TikTok/Reels | `⚡ Peak Energy` |
| `cinematic` | **Cinematic** | `16:9` | 00.00s – 30.00s (30s) | Full 16:9 master sequence with widescreen aesthetic | `🎬 16:9 Master` |
| `raw_pov` | **Raw POV** | `original` | 00.00s – 30.00s (30s) | Unmodified raw capture aspect ratio | `📹 Raw POV` |

**Behavior on Selection**:
- Sets `activeCut` and `cropRatio`.
- Auto-populates `inPoint` and `outPoint` sliders.
- Seeks video player `currentTime` to `inPoint`.

### 4.3 Dual-Handle Trim Slider & Frame-Scrub Controls
- **Dual Range Controls**:
  - In-Point Slider: `min=0`, `max=outPoint - 0.5`, `step=0.1`
  - Out-Point Slider: `min=inPoint + 0.5`, `max=duration`, `step=0.1`
- **Micro-Adjustment Steppers**: `[-0.1s]` and `[+0.1s]` buttons for frame-accurate adjustments.
- **Timestamp Displays**:
  - In Point: `00:05.00`
  - Out Point: `00:15.00`
  - Total Duration: `10.00s`
- **Playback Bounding**: When video playback crosses `outPoint`, playback auto-loops back to `inPoint`.

### 4.4 Instagram-Style Text Overlay
- **Input Field**: `<input type="text" placeholder="Add viral hook text (e.g., 🔥 CRAZY DROP AT ULTRA)..." />`
- **Position Selector**: `Top` (default for Reels hooks), `Center`, `Bottom`.
- **Live DOM Preview**: Absolute overlay positioned directly on top of the HTML5 video viewport:
  - Font styling: `font-black uppercase tracking-wider text-yellow-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] bg-black/50 px-3 py-1 rounded-md`
- **Quick Preset Badges**: Clickable chips (e.g., `"🔥 CRAZY DROP"`, `"⚡ WAIT FOR IT"`, `"🔊 VOLUME UP"`) to instantly inject viral hooks.

### 4.5 "Render & Publish" Workflow & State Handling
- **Action**: Clicking "Render & Publish" dispatches payload to API:
  ```json
  {
    "source_file": "clip_ultra_drop_4k_01.mp4",
    "in_point": 5.0,
    "out_point": 15.0,
    "crop_ratio": "9:16",
    "text_overlay": "🔥 CRAZY DROP AT ULTRA"
  }
  ```
- **Execution States**:
  - `IDLE`: Normal state with active render button.
  - `RENDERING`: Button disabled, glowing spinner, message: `"Compiling FFmpeg 4K Master..."`.
  - `COMPLETED`: Success alert with output path (`renders/clip_ultra_drop_4k_01_9_16.mp4`), execution timestamp, and download/preview button.
  - `FAILED`: Error banner with retry option and DLQ incident quarantine link.

---

## 5. API Client Layer Extensions (`dashboard/src/lib/api.ts`)

### 5.1 Type Definitions
```typescript
export interface MediaRenderRequest {
  source_file: string;
  in_point: number;
  out_point: number;
  crop_ratio: '9:16' | '16:9' | 'original' | string;
  text_overlay?: string;
}

export interface MediaRenderResult {
  job_id: string;
  status: 'COMPLETED' | 'RENDERING' | 'QUEUED' | 'FAILED';
  output_file: string;
  source_file: string;
  in_point: number;
  out_point: number;
  crop_ratio: string;
  text_overlay?: string;
  command?: string;
  rendered_at: number;
}
```

### 5.2 Client Function Implementation
```typescript
export async function renderMediaVideo(payload: MediaRenderRequest): Promise<MediaRenderResult> {
  const cleanSource = payload.source_file.replace(/\.[^/.]+$/, '');
  const cleanRatio = payload.crop_ratio.replace(':', '_');
  const mockResult: MediaRenderResult = {
    job_id: `render_${Math.random().toString(16).substring(2, 10)}`,
    status: 'COMPLETED',
    output_file: `renders/${cleanSource}_${cleanRatio}.mp4`,
    source_file: payload.source_file,
    in_point: payload.in_point,
    out_point: payload.out_point,
    crop_ratio: payload.crop_ratio,
    text_overlay: payload.text_overlay || '',
    command: `ffmpeg -ss ${payload.in_point} -to ${payload.out_point} -i ${payload.source_file} ...`,
    rendered_at: Date.now(),
  };

  return safeFetch<MediaRenderResult>(
    '/api/v1/media/render',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    mockResult
  );
}
```

---

## 6. Frontend Test Plan & Loud Assertions

### 6.1 New Test Suite: `dashboard/__tests__/media-studio.test.tsx`
The test suite will validate the full lifecycle of `MediaStudio.tsx` using `@testing-library/react` and Vitest:

1. **Test 1: Initial Render & DOM Construction**
   - Assert HTML5 `<video>` tag is present with initial source.
   - Assert 3 cut preset buttons ("Hype Drop", "Cinematic", "Raw POV") are rendered.
   - Assert dual trim handles (in-point and out-point) are initialized.
   - Assert text overlay input is empty or has default placeholder.
   - Assert "Render & Publish" button is rendered and enabled.

2. **Test 2: Base Cut Preset Switching**
   - Click "Hype Drop" -> Verify 9:16 aspect ratio selected, in-point updated to 5.0, out-point to 15.0.
   - Click "Cinematic" -> Verify 16:9 aspect ratio selected, in-point updated to 0.0, out-point to 30.0.
   - Click "Raw POV" -> Verify original aspect ratio selected.

3. **Test 3: Dual Trim Slider & Micro-Adjusters**
   - Change in-point input -> verify timestamp display updates (e.g., `00:08.00`).
   - Change out-point input -> verify timestamp display updates (e.g., `00:22.00`).
   - Verify duration calculation matches `out_point - in_point`.

4. **Test 4: Instagram-Style Text Overlay Live Preview**
   - Type `"🔥 BASS DROP 2026"` in text overlay field.
   - Assert that text appears live inside the video overlay container.
   - Toggle position (Top / Center / Bottom) and verify CSS alignment classes.

5. **Test 5: Render & Publish API Trigger & Status Transition**
   - Click "Render & Publish".
   - Verify rendering spinner / loading state is shown.
   - Wait for completion -> verify success banner displays output file name (`renders/...mp4`) and `COMPLETED` status.

6. **Test 6: Offline Resiliency & Error Recovery**
   - Mock API rejection / network error.
   - Click "Render & Publish".
   - Verify error notification is caught and displayed without crashing the component.

### 6.2 Regression Test Updates
- **`dashboard/__tests__/api-client.test.ts`**: Add unit test verifying `renderMediaVideo()` returns proper mock result and formats payload correctly.
- **`dashboard/__tests__/layout.test.tsx`**: Update layout integration test to verify the new "Media Studio" navigation tab and seamless view switching.

---

## 7. Implementation File Roadmap

| File Path | Role | Action |
|---|---|---|
| `dashboard/src/lib/api.ts` | API Client | Add `MediaRenderRequest`, `MediaRenderResult`, and `renderMediaVideo()` with deterministic mock fallback. |
| `dashboard/src/components/MediaStudio.tsx` | Web Editor Component | Implement full React component with video player, 3 cuts, dual trim slider, text overlay, and render button. |
| `dashboard/src/app/page.tsx` | Main Dashboard Layout | Add `'studio'` to `TabType`, add navigation tab button, and mount `MediaStudio` in studio/media views. |
| `dashboard/__tests__/media-studio.test.tsx` | Test Suite | Implement comprehensive unit & integration tests for all Media Studio features. |
| `dashboard/__tests__/api-client.test.ts` | Test Suite | Add test for `renderMediaVideo` API client method. |
| `dashboard/__tests__/layout.test.tsx` | Test Suite | Update layout test to verify Media Studio tab navigation. |

---

## 8. Conclusion & Recommendation

The Next.js dashboard codebase is exceptionally clean, well-modularized, and ready for the integration of `MediaStudio.tsx`. The proposed design strictly adheres to all user requirements and architectural guardrails (React 19, Tailwind CSS v4, ErrorBoundary isolation, deterministic mock fallbacks, and 100% Vitest coverage).
