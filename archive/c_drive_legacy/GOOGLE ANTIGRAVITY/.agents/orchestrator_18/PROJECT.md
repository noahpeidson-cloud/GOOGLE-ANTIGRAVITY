# Project: Unified Ops Hub — Media Gallery & Catalog System

## Architecture
- **Database Layer**: SQLite (`media_catalog.db`) managed by `MediaCatalogManager` in `unified_ops_hub/gateway/media_catalog.py` with WAL mode, `threading.RLock()`, foreign key cascading (`ON DELETE CASCADE`), indexes on `album_id` and status columns, and triggers for atomic `media_count` tracking.
- **Backend API Gateway**: FastAPI in `unified_ops_hub/gateway/app.py` exposing REST endpoints for Albums, Media items, Catalog queries, and batch ML grading triggers.
- **Static Streaming**: FastAPI mount `/proxies` serving 720p H.264 proxy files supporting HTTP 206 Partial Content range requests for zero-latency video scrubbing.
- **Frontend Dashboard**: Next.js 16 (App Router) + React 19 + Tailwind CSS 4 in `unified_ops_hub/dashboard/` featuring Google Photos-style album grid layout, zero-latency hover scrubbing, multi-selection state machine, and floating action dock.
- **ML Grading Pipeline**: Spark/Gemini grading execution with EVPI formula scoring, killswitch enforcement, and DLQ quarantine containment.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | SQLite Catalog DDL & Migration | Define `albums` and `media` tables with foreign keys, indexes, check constraints, and triggers | M1 | Survey / R1 |
| 2 | MediaCatalogManager Python Module | Thread-safe SQLite manager class with WAL mode, CRUD methods, and join queries | M1 | Survey / R1 |
| 3 | Backend REST Endpoints | FastAPI routes for `GET /api/v1/media/albums`, `GET /api/v1/media/albums/{id}/media`, `GET /api/v1/media/catalog` | M1 | Survey / R1 |
| 4 | Backend DB Verification Test | Deterministic test `test_media_catalog_db.py` verifying mock Album + 3 Media entries with `G:\...` paths and `SELECT` join | M1 | Acceptance Criteria 1 |
| 5 | Media Gallery Next.js Component | Responsive Google Photos-style gallery layout with album headers and video grid | M2 | Survey / R2 |
| 6 | Zero-Latency Video Scrubbing | Hover/cursor scrubbing using HTML5 `<video>` and `requestAnimationFrame` | M2 | Survey / R2 |
| 7 | Dashboard Navigation Integration | Add `'gallery'` tab to `src/app/page.tsx` and connect with `'studio'` tab | M2 | Survey / R2 |
| 8 | UI Video Rendering Test | Programmatic React test verifying `<video>` elements render with proxy `src` | M2 | Acceptance Criteria 2 |
| 9 | Multi-Selection State Machine | Per-item checkboxes, album "Select All" toggle, and selected count tracker | M3 | Survey / R3 |
| 10 | Batch Grading Trigger Action Dock | Floating action dock with "Grade Selected" button dispatching POST request | M3 | Survey / R3 |
| 11 | API Client Batch Grading Method | Frontend API client method `gradeMediaBatch()` with toast notifications | M3 | Survey / R3 |
| 12 | UI Trigger Verification Test | Programmatic React test confirming clicking "Grade Selected" fires mock API POST with IDs | M3 | Acceptance Criteria 3 |
| 13 | 4-Tier Opaque-box E2E Suite | Comprehensive E2E test suite covering feature, boundary, cross-feature, and real-world tiers | M4 | Survey / E2E Track |
| 14 | Adversarial Hardening (Tier 5) | White-box stress testing for SQLite concurrency, special characters, and empty states | M4 | Survey / Final Milestone |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | SQLite Catalog DB & Backend API | `media_catalog.db` DDL, `MediaCatalogManager`, FastAPI routes, AC1 test | none | PLANNED |
| M2 | Next.js Media Gallery UI | `MediaGallery.tsx`, zero-latency scrubbing, dashboard tab, AC2 test | M1 | PLANNED |
| M3 | Grading Trigger & Selection State | Multi-selection state, "Grade Selected" dock, API batch trigger, AC3 test | M2 | PLANNED |
| M4 | E2E Verification & Adversarial Hardening | 100% pass across Tiers 1-4 and Tier 5 adversarial stress tests | M1, M2, M3 | PLANNED |

## Interface Contracts
### MediaCatalogManager ↔ Gateway
```python
class MediaCatalogManager:
    def __init__(self, db_path: str = "media_catalog.db"): ...
    def create_schema(self) -> None: ...
    def create_album(self, title: str, description: Optional[str] = None) -> str: ...
    def add_media_item(self, album_id: str, filename: str, proxy_path: str, raw_path: Optional[str] = None, duration: float = 0.0, resolution: str = "1080p") -> str: ...
    def get_albums(self) -> List[Dict[str, Any]]: ...
    def get_album_media(self, album_id: str) -> List[Dict[str, Any]]: ...
    def get_full_catalog(self) -> List[Dict[str, Any]]: ...
    def update_grading_status(self, media_ids: List[str], status: str, scores: Optional[Dict[str, float]] = None) -> None: ...
```

### Gateway ↔ Frontend REST Endpoints
- `GET /api/v1/media/albums` -> `[ { "id": "alb_001", "title": "Ultra 2026", "media_count": 3, "created_at": "..." } ]`
- `GET /api/v1/media/albums/{album_id}/media` -> `[ { "id": "med_001", "album_id": "alb_001", "filename": "clip.mp4", "proxy_path": "/proxies/clip.mp4", "raw_path": "G:\\...", "grading_status": "PENDING" } ]`
- `POST /api/v1/ml/grade/batch` (or `POST /api/v1/media/grade/batch`) -> `{ "media_ids": ["med_001", "med_002"] }` -> returns `{ "status": "QUEUED", "job_id": "job_123", "queued_count": 2 }`

## Code Layout
- `unified_ops_hub/gateway/media_catalog.py` (Worker M1)
- `unified_ops_hub/gateway/app.py` (Worker M1)
- `unified_ops_hub/tests/test_media_catalog_db.py` (Worker M1)
- `unified_ops_hub/tests/test_media_gallery_api.py` (Worker M1)
- `unified_ops_hub/dashboard/src/components/MediaGallery.tsx` (Worker M2, M3)
- `unified_ops_hub/dashboard/src/app/page.tsx` (Worker M2)
- `unified_ops_hub/dashboard/src/lib/api.ts` (Worker M2, M3)
- `unified_ops_hub/dashboard/__tests__/media-gallery.test.tsx` (Worker M2, M3)
- `unified_ops_hub/tests/test_e2e_gallery.py` (E2E Test Writer / M4)
