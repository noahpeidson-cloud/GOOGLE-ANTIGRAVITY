# Project: Unified Ops Hub — Media Studio

## Architecture
The Media Studio adds a human-in-the-loop video editing and AI proxy/cut generation capability to the Unified Ops Hub.

```
[Raw 4K / Ingested Video]
       │
       ▼
[ml_agent/editor.py: MediaEditor]
       ├── Generates 720p Proxy (.mp4)
       └── Analyzes Audio Waveform Peak -> Generates 3 Cuts JSON:
             * hype_drop (Loudest peak, 9:16 crop)
             * cinematic (Full duration, 16:9 crop)
             * raw_pov   (Full duration, native aspect ratio)
       │
       ▼
[dashboard/src/components/MediaStudio.tsx]
       ├── Loads 720p Proxy in HTML5 Video Player
       ├── 3 Cut Toggle Buttons (Hype, Cinematic, Raw)
       ├── Dual-Handle In/Out Point Scrubbing Trim Slider
       ├── Text Overlay Input Box
       └── "Render & Publish" Button
       │
       ▼
[gateway/app.py -> POST /api/v1/media/render]
       │
       ▼
[gateway/renderer.py: FFmpegRenderer]
       └── Executes FFmpeg against 4K Raw File
             - Sub-second trimming (-ss in_point, -t duration)
             - Cropping (9:16 / 16:9 / native)
             - Escaped text overlay rendering
             - Outputs final MP4 to `renders/`
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | AI Proxy Generation | Subprocess FFmpeg downscaling to 720p H.264 Faststart MP4 | M1 | R1 (ORIGINAL_REQUEST §1) |
| 2 | Audio Peak DSP & 3 Cuts Generator | In-memory PCM audio extraction + sliding window RMS energy argmax to produce `hype_drop`, `cinematic`, `raw_pov` | M1 | R1 (ORIGINAL_REQUEST §1) |
| 3 | Headless FFmpeg Renderer Engine | Subprocess FFmpeg pipeline supporting trim, 9:16/16:9 crop, scale, text overlay, outputting to `renders/` | M2 | R2 (ORIGINAL_REQUEST §2) |
| 4 | FastAPI Render API Endpoint | `POST /api/v1/media/render` with Pydantic validation, CORS, error handling, and sync/async options | M2 | R2 (ORIGINAL_REQUEST §2) |
| 5 | Media Studio React Component | HTML5 video player, 3 preset toggle buttons, dual-handle trim slider, text overlay input, Render & Publish button | M3 | R3 (ORIGINAL_REQUEST §3) |
| 6 | Dashboard Navigation & API Client | Integration into `page.tsx` tab system and `src/lib/api.ts` `renderMediaVideo()` method | M3 | R3 (ORIGINAL_REQUEST §3) |
| 7 | Backend Unit & Integration Tests | `tests/test_media_editor.py` and `tests/test_ffmpeg_renderer.py` covering all edge cases | M4 | Acceptance Criteria |
| 8 | Frontend Vitest Component Tests | `dashboard/__tests__/media-studio.test.tsx` verifying render, presets, scrubbing, API interaction | M4 | Acceptance Criteria |
| 9 | Opaque-Box E2E & Adversarial Suite | Multi-tier test harness validating full flow, silence handling, short clip clamping, text escaping | M4 | Project E2E Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | AI Proxy & Cut Generator | `ml_agent/editor.py`, `ml_agent/__init__.py`, `tests/test_media_editor.py` | None | DONE |
| M2 | Headless FFmpeg Renderer & API | `gateway/renderer.py`, `gateway/app.py`, `tests/test_ffmpeg_renderer.py` | None | DONE |
| M3 | Media Studio Frontend Web Editor | `dashboard/src/components/MediaStudio.tsx`, `dashboard/src/lib/api.ts`, `dashboard/src/app/page.tsx`, `dashboard/__tests__/media-studio.test.tsx` | M1, M2 (Interface Contracts) | IN_PROGRESS |
| M4 | E2E Integration & Verification | Full test suite execution across backend (`pytest`) and frontend (`vitest`), adversarial hardening | M1, M2, M3 | PLANNED |

## Interface Contracts

### MediaEditor ↔ Gateway / Dashboard
- **JSON Metadata Format**:
```json
{
  "source_file": "raw_video.mp4",
  "proxy_file": "proxies/raw_video_proxy.mp4",
  "duration": 30.0,
  "cuts": {
    "hype_drop": {
      "in_point": 5.0,
      "out_point": 20.0,
      "crop_ratio": "9:16",
      "label": "Hype Drop (Audio Peak)",
      "target_resolution": "1080x1920"
    },
    "cinematic": {
      "in_point": 0.0,
      "out_point": 30.0,
      "crop_ratio": "16:9",
      "label": "Cinematic (16:9)",
      "target_resolution": "1920x1080"
    },
    "raw_pov": {
      "in_point": 0.0,
      "out_point": 30.0,
      "crop_ratio": "original",
      "label": "Raw POV (Original)",
      "target_resolution": "original"
    }
  }
}
```

### Dashboard ↔ Gateway `POST /api/v1/media/render`
- **Request Payload**:
```json
{
  "source_file": "data/sample_4k.mp4",
  "in_point": 5.0,
  "out_point": 20.0,
  "crop_ratio": "9:16",
  "text_overlay": "🔥 HYPE MOMENT",
  "sync": true
}
```
- **Response Payload**:
```json
{
  "status": "completed",
  "render_id": "render_1740528000_abc123",
  "output_file": "renders/render_1740528000_abc123.mp4",
  "duration": 15.0,
  "crop_ratio": "9:16",
  "text_overlay": "🔥 HYPE MOMENT",
  "message": "Render completed successfully"
}
```

## Code Layout
- `ml_agent/editor.py`: Contains `MediaEditor` class (720p proxy downscaling, in-memory audio DSP peak detection, 3 cuts metadata generation).
- `ml_agent/__init__.py`: Exports `MediaEditor`.
- `gateway/renderer.py`: Contains `FFmpegRenderer` class (command compilation, escaping, execution, output verification).
- `gateway/app.py`: Contains FastAPI app, mounts `/api/v1/media/render`, CORS middleware, static file serving.
- `dashboard/src/components/MediaStudio.tsx`: React Media Studio UI component.
- `dashboard/src/lib/api.ts`: Frontend HTTP client methods.
- `dashboard/src/app/page.tsx`: Navigation bar, tab integration.
- `tests/test_media_editor.py`: Backend tests for proxy and cut generation.
- `tests/test_ffmpeg_renderer.py`: Backend tests for headless FFmpeg renderer and render API.
- `dashboard/__tests__/media-studio.test.tsx`: Frontend Vitest component tests.
