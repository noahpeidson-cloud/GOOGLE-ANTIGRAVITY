# Technical Analysis: Testing & Verification Strategy for Unified Ops Hub Media Gallery

## 1. Executive Summary & Acceptance Criteria Mapping

The **Unified Ops Hub Media Gallery** project introduces a Google Photos-style media management interface to ingest, organize, display, and trigger raw video assets for Gemini Omni ML grading. In accordance with **Rule R2 (The Zero-Discretion Mandate / Leash Protocol)**, this analysis establishes an immutable, deterministic testing framework and verification specification to prevent subjective self-certification.

### Acceptance Criteria Matrix

| Acceptance Criterion | Verification Method | Target Test Harness | Pass Condition |
|----------------------|---------------------|---------------------|----------------|
| **1. Backend DB Verification** | `test_media_catalog_db.py` | `python -m pytest tests/test_media_catalog_db.py -v` | Schema initializes `albums` + `media` tables in WAL mode, inserts mock Album + 3 Media rows with `G:\...` paths, and successfully queries via `SELECT` JOIN with 100% field assertions. |
| **2. UI Rendering Verification** | `media-gallery.test.tsx` | `npm test` (`npx vitest run __tests__/media-gallery.test.tsx`) | React Testing Library renders `MediaGallery`, verifies presence of `<video>` elements with exact proxy `src` attributes, duration badges, and status pills. |
| **3. Trigger Verification** | `media-gallery.test.tsx` + `test_media_gallery_api.py` | Vitest + Pytest TestClient | Verifies multi-item selection state, "Grade Selected" button enablement, dispatch of `POST` request with array of media IDs, loading state, and DLQ exception isolation. |

---

## 2. Existing Test Frameworks & Execution Environment

### 2.1 Backend Python Testing Infrastructure
- **Python Runtime**: `Python 3.13.14 (win32)` located at Windows App execution path.
- **Test Runner**: `pytest 9.1.1` with `pluggy-1.6.0`.
- **Installed Plugins**: `pytest-asyncio 1.4.0`, `pytest-mock 3.15.1`, `anyio 4.14.2`.
- **Execution Command**:
  ```powershell
  # MUST execute via python -m pytest (Rule R16/R18; bare 'pytest' is not in Windows system PATH)
  python -m pytest tests/test_media_catalog_db.py tests/test_media_gallery_api.py -v
  ```
- **Test Isolation Standards**:
  - Use `tmp_path` fixture for per-test SQLite database files to guarantee zero shared state across tests.
  - Enable SQLite `PRAGMA foreign_keys = ON;` and `PRAGMA journal_mode = WAL;` on every test connection.
  - Mock external hardware/network dependencies (FFmpeg, Gemini API, ADB) using `unittest.mock.patch`.

### 2.2 Frontend React/Next.js Testing Infrastructure
- **Node & npm Runtime**: Node `v26.7.0`, npm `11.19.0`.
- **Test Runner**: Vitest `v3.2.7` / `v3.0.5` configured with `jsdom 26.0.0`.
- **Testing Libraries**:
  - `@testing-library/react`: `^16.2.0`
  - `@testing-library/jest-dom`: `^6.6.3`
  - `@testing-library/user-event`: `^14.6.1`
- **Configuration & Setup**:
  - `vitest.config.ts`: Defines `globals: true`, `environment: 'jsdom'`, `setupFiles: ['./src/setupTests.ts']`, and path aliases `@/` -> `./src/`.
  - `src/setupTests.ts`: Global mocks for `matchMedia`, `ResizeObserver`, and `EventSource`.
- **Execution Command**:
  ```powershell
  npm test # Executes vitest run in dashboard directory
  npx vitest run __tests__/media-gallery.test.tsx
  ```

---

## 3. Backend Database Architecture & Verification Design

### 3.1 SQLite Schema Specification (`media_catalog.db`)

To support Google Photos-style album grouping, zero-latency local proxy streaming, and ML grading tracking, the schema must enforce referential integrity and strict status domains:

```sql
-- Enforce Foreign Key Constraints
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- 1. Albums Table
CREATE TABLE IF NOT EXISTS albums (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    event_date TEXT NOT NULL,          -- ISO 8601 string 'YYYY-MM-DD'
    source_device TEXT DEFAULT 'Android_S24_Ultra',
    created_at REAL NOT NULL,          -- Unix epoch timestamp
    updated_at REAL NOT NULL,
    total_media_count INTEGER DEFAULT 0,
    graded_media_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'INGESTED' 
        CHECK(status IN ('INGESTED', 'GRADING_IN_PROGRESS', 'GRADED', 'ARCHIVED'))
);

-- 2. Media Table
CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY,
    album_id TEXT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    raw_path TEXT NOT NULL,            -- Local G: drive raw file path
    proxy_path TEXT NOT NULL,          -- Local G: drive 720p proxy path
    duration_sec REAL NOT NULL DEFAULT 0.0,
    resolution TEXT DEFAULT '1080x1920',
    fps REAL DEFAULT 60.0,
    file_size_bytes INTEGER DEFAULT 0,
    upload_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK(upload_status IN ('PENDING', 'UPLOADING', 'UPLOADED', 'FAILED')),
    grading_status TEXT NOT NULL DEFAULT 'UNGRADED'
        CHECK(grading_status IN ('UNGRADED', 'QUEUED', 'GRADING', 'GRADED', 'FAILED')),
    evpi_score REAL,                   -- Expected Value of Potential Impact (0.0 - 100.0)
    grading_verdict TEXT 
        CHECK(grading_verdict IN ('VIRAL_READY', 'HIGH_POTENTIAL', 'MODERATE_REACH', 'LOW_REACH', NULL)),
    grading_metadata_json TEXT,        -- JSON breakdown of HRV, DPAW, ADR_SFD, CKE_MVE, LTSS
    created_at REAL NOT NULL,
    graded_at REAL
);

-- 3. High-Performance Indexes
CREATE INDEX IF NOT EXISTS idx_media_album_id ON media(album_id);
CREATE INDEX IF NOT EXISTS idx_media_upload_status ON media(upload_status);
CREATE INDEX IF NOT EXISTS idx_media_grading_status ON media(grading_status);
CREATE INDEX IF NOT EXISTS idx_albums_event_date ON albums(event_date DESC);
```

### 3.2 Python Database Verification Script Specification (`tests/test_media_catalog_db.py`)

The verification script must use Loud Assertions to execute the exact acceptance criteria:

```python
"""Loud Assertion verification suite for media_catalog.db (Acceptance Criterion 1)."""
import os
import sqlite3
import pytest
from pathlib import Path

def test_media_catalog_schema_and_relational_join(tmp_path):
    """Verifies schema initialization, mock Album + 3 Media insertion, and relational SELECT query."""
    db_file = tmp_path / "media_catalog.db"
    
    # 1. Initialize SQLite connection with WAL mode and Foreign Keys
    conn = sqlite3.connect(str(db_file), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    
    # Execute Schema DDL
    with open("gateway/schema_media_catalog.sql", "r") if Path("gateway/schema_media_catalog.sql").exists() else ... as f:
        # Schema definition applied
        ...
    
    # 2. Insert Mock Album
    album_id = "album_ultra_2026_01"
    conn.execute(
        """
        INSERT INTO albums (id, title, description, event_date, source_device, created_at, updated_at, total_media_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (album_id, "Ultra Music Festival 2026 Raw Drops", "Mainstage 4K POV recordings", "2026-08-25", "Android_S24_Ultra", 1756166400.0, 1756166400.0, 3)
    )
    
    # 3. Insert 3 Mock Media Entries with Local G: Drive Paths
    mock_media = [
        ("media_001", album_id, "VID_20260825_001.mp4", 
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\VID_20260825_001.mp4",
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\proxies\VID_20260825_001_proxy.mp4",
         15.4, "1080x1920", 60.0, 48200100, "PENDING", "UNGRADED", 1756166410.0),
        ("media_002", album_id, "VID_20260825_002.mp4", 
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\VID_20260825_002.mp4",
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\proxies\VID_20260825_002_proxy.mp4",
         28.2, "1080x1920", 60.0, 89100200, "UPLOADED", "UNGRADED", 1756166450.0),
        ("media_003", album_id, "VID_20260825_003.mp4", 
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\VID_20260825_003.mp4",
         r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\proxies\VID_20260825_003_proxy.mp4",
         12.0, "1920x1080", 30.0, 35000400, "PENDING", "UNGRADED", 1756166500.0),
    ]
    conn.executemany(
        """
        INSERT INTO media (id, album_id, file_name, raw_path, proxy_path, duration_sec, resolution, fps, file_size_bytes, upload_status, grading_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        mock_media
    )
    conn.commit()
    
    # 4. Query via Relational SELECT Join
    cursor = conn.execute(
        """
        SELECT 
            a.id AS album_id,
            a.title AS album_title,
            a.event_date,
            m.id AS media_id,
            m.file_name,
            m.raw_path,
            m.proxy_path,
            m.duration_sec,
            m.upload_status,
            m.grading_status
        FROM albums a
        JOIN media m ON a.id = m.album_id
        WHERE a.id = ?
        ORDER BY m.id ASC;
        """,
        (album_id,)
    )
    rows = cursor.fetchall()
    
    # Loud Assertions
    assert len(rows) == 3, f"LOUD ASSERTION FAILURE: Expected 3 media rows, got {len(rows)}"
    assert rows[0]["album_title"] == "Ultra Music Festival 2026 Raw Drops"
    assert rows[0]["media_id"] == "media_001"
    assert rows[0]["proxy_path"].startswith(r"G:\My Drive\GOOGLE ANTIGRAVITY")
    assert rows[1]["upload_status"] == "UPLOADED"
    assert rows[2]["grading_status"] == "UNGRADED"
    
    conn.close()
```

---

## 4. Frontend UI Rendering & Trigger Verification Design

### 4.1 Component Hierarchy (`dashboard/src/components/MediaGallery/`)
- `MediaGallery.tsx`: Central container managing albums list, multi-selection state (`Set<string>`), grading action bar, and API dispatch.
- `AlbumSection.tsx`: Renders album header (title, event date, media count, "Select All" toggle) and responsive CSS grid (`grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4`).
- `MediaCard.tsx`: Renders individual media tile containing:
  - Checkbox selection overlay (`data-testid={`media-checkbox-${media.id}`}`)
  - HTML5 `<video>` element (`data-testid={`media-video-${media.id}`}`) with `src={media.proxy_path}`
  - Duration pill (e.g. `15.4s`), Resolution badge (`1080x1920`)
  - Status badge (e.g. `PENDING`, `GRADED (88.5 EVPI)`)
  - Interactive hover preview / play on hover for zero-latency local scrubbing.
- `GradingActionBar.tsx`: Floating action bar appearing when `selectedMediaIds.size > 0` with:
  - Selected count badge (`2 items selected`)
  - "Clear Selection" button
  - "Grade Selected" button (`data-testid="grade-selected-button"`) with sparkle icon.

### 4.2 Vitest Component Test Specification (`dashboard/__tests__/media-gallery.test.tsx`)

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MediaGallery } from '@/components/MediaGallery';
import * as api from '@/lib/api';

describe('MediaGallery Component & ML Grading Trigger Suite', () => {
  const mockAlbums = [
    {
      id: 'album_ultra_01',
      title: 'Ultra Miami 2026 Mainstage',
      event_date: '2026-08-25',
      media: [
        {
          id: 'media_001',
          album_id: 'album_ultra_01',
          file_name: 'VID_001.mp4',
          proxy_path: '/proxies/VID_001_proxy.mp4',
          duration_sec: 15.4,
          upload_status: 'PENDING',
          grading_status: 'UNGRADED',
        },
        {
          id: 'media_002',
          album_id: 'album_ultra_01',
          file_name: 'VID_002.mp4',
          proxy_path: '/proxies/VID_002_proxy.mp4',
          duration_sec: 28.2,
          upload_status: 'UPLOADED',
          grading_status: 'UNGRADED',
        },
        {
          id: 'media_003',
          album_id: 'album_ultra_01',
          file_name: 'VID_003.mp4',
          proxy_path: '/proxies/VID_003_proxy.mp4',
          duration_sec: 12.0,
          upload_status: 'PENDING',
          grading_status: 'GRADED',
          evpi_score: 88.5,
          grading_verdict: 'VIRAL_READY',
        },
      ],
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Google Photos-style album header and maps over media to render <video> elements', () => {
    render(<MediaGallery initialAlbums={mockAlbums} />);

    // Verify Album Title
    expect(screen.getByText('Ultra Miami 2026 Mainstage')).toBeInTheDocument();

    // Verify exactly 3 HTML5 video elements rendered
    const video1 = screen.getByTestId('media-video-media_001') as HTMLVideoElement;
    const video2 = screen.getByTestId('media-video-media_002') as HTMLVideoElement;
    const video3 = screen.getByTestId('media-video-media_003') as HTMLVideoElement;

    expect(video1).toBeInTheDocument();
    expect(video1.getAttribute('src')).toBe('/proxies/VID_001_proxy.mp4');
    expect(video2.getAttribute('src')).toBe('/proxies/VID_002_proxy.mp4');
    expect(video3.getAttribute('src')).toBe('/proxies/VID_003_proxy.mp4');

    // Verify duration and status badges
    expect(screen.getByText('15.4s')).toBeInTheDocument();
    expect(screen.getByText('28.2s')).toBeInTheDocument();
    expect(screen.getByText('88.5 EVPI')).toBeInTheDocument();
  });

  it('manages selection state and fires POST request with selected media IDs on "Grade Selected" click', async () => {
    const gradeSpy = vi.spyOn(api, 'gradeMediaBatch').mockResolvedValue({
      status: 'QUEUED',
      job_ids: ['job_001', 'job_002'],
      graded_count: 2,
    });

    render(<MediaGallery initialAlbums={mockAlbums} />);

    // Initially Grade Selected button is not active / disabled
    expect(screen.queryByTestId('grade-selected-button')).toBeNull();

    // Select Media 1 and Media 2
    const checkbox1 = screen.getByTestId('media-checkbox-media_001');
    const checkbox2 = screen.getByTestId('media-checkbox-media_002');

    fireEvent.click(checkbox1);
    fireEvent.click(checkbox2);

    // Grade Selected button appears with count (2)
    const gradeButton = screen.getByTestId('grade-selected-button');
    expect(gradeButton).toBeInTheDocument();
    expect(gradeButton).toHaveTextContent(/Grade Selected \(2\)/i);

    // Click Grade Selected
    fireEvent.click(gradeButton);

    // Assert mock API call
    await waitFor(() => {
      expect(gradeSpy).toHaveBeenCalledTimes(1);
      expect(gradeSpy).toHaveBeenCalledWith(['media_001', 'media_002']);
    });

    // Verify UI enters loading state
    expect(screen.getByText(/Submitting for grading.../i)).toBeInTheDocument();
  });
});
```

---

## 5. 4-Tier Opaque-Box E2E & Adversarial Testing Strategy

In compliance with `TEST_INFRA.md` standards, the Media Gallery testing matrix spans 4 distinct tiers:

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 4: Real-World Workloads, Concurrency & Hardware Disconnect │
├─────────────────────────────────────────────────────────────┤
│  Tier 3: Cross-Feature Integration (Ingest -> DB -> UI -> ML)│
├─────────────────────────────────────────────────────────────┤
│  Tier 2: Boundary Value Analysis & Edge Cases (0 items, 500+)│
├─────────────────────────────────────────────────────────────┤
│  Tier 1: Core Feature Coverage (Acceptance Criteria 1, 2, 3) │
└─────────────────────────────────────────────────────────────┘
```

### Tier 1: Feature Coverage (Core Requirements)
- **T1.1**: SQLite schema initialization (`albums`, `media`, foreign keys, indexes).
- **T1.2**: Mock Album & Media insertion with local `G:\...` paths.
- **T1.3**: Relational `SELECT` join querying media records by album.
- **T1.4**: React Gallery component rendering `<video>` tags with valid proxy URLs.
- **T1.5**: Checkbox selection toggle and count state synchronization.
- **T1.6**: "Grade Selected" button dispatching `POST /api/v1/ml/grade-batch`.

### Tier 2: Boundary Value Analysis & Edge Cases
- **T2.1 (Empty Album)**: Album with 0 media entries displays empty state banner ("No raw media ingested yet") without crashing.
- **T2.2 (Large Album Scalability)**: Album with 500+ media items renders efficiently with virtualized scrolling / lazy loading without detached DOM node leaks.
- **T2.3 (Special Characters in File Paths)**: Local file paths containing spaces, brackets, hashes, and non-ASCII chars (e.g. `G:\My Drive\raw\Clip #1 [Ultra] 100% (4K).mp4`) are correctly escaped and served.
- **T2.4 (Zero-Length / Corrupted Media)**: Media with `duration_sec = 0.0` or broken video source renders fallback thumbnail with `<video onError={...}>` without breaking the grid.
- **T2.5 (Zero-Selection Trigger Guardrail)**: Attempting to trigger grading when 0 items are selected is strictly blocked on frontend and rejected with `422 Unprocessable Entity` on backend.
- **T2.6 (Unicode & Emoji Album Titles)**: Album titles like `🔥 Ultra Miami 2026 (Day 1 - Mainstage ID's)` persist and render with exact string preservation.

### Tier 3: Cross-Feature Integration
- **T3.1 (Ingestion to Gallery Integration)**: Android Wi-Fi Ingestion daemon writes media record to SQLite -> Gateway `/api/v1/gallery/albums` reflects new items -> Gallery UI updates in real-time.
- **T3.2 (ML Grading Closed-Loop)**: User clicks "Grade Selected" -> Gateway invokes `ml_agent.grade_video()` -> Updates `media` record `grading_status = 'GRADED'`, `evpi_score = 92.4`, `grading_verdict = 'VIRAL_READY'` -> Gallery badge turns green.
- **T3.3 (DLQ Exception Isolation)**: When ML grading encounters a corrupted video file, Gateway catches exception, isolates record to `unified_ops_hub_dlq.db`, and sets `media.grading_status = 'FAILED'` without affecting other batch items.

### Tier 4: Real-World Workload & Concurrency
- **T4.1 (SQLite Concurrency Stress)**: 5 background ingestion worker threads write new media rows simultaneously while 10 concurrent UI clients query `SELECT JOIN` albums under SQLite WAL mode (verifying zero `database is locked` errors).
- **T4.2 (Rapid Click Debounce)**: Rapidly double-clicking "Grade Selected" dispatches exactly 1 network request.
- **T4.3 (G: Drive Workspace Disconnect Simulation / Rule R19)**: If the `G:` drive volume is unmounted during proxy streaming, UI displays actionable warning ("Media volume disconnected; restart Google Drive Desktop") and fails gracefully.

---

## 6. Potential Failure Modes & Mitigation Table

| Potential Failure Mode | Root Cause | Impact | Deterministic Prevention / Mitigation |
|------------------------|------------|--------|---------------------------------------|
| `sqlite3.OperationalError: database is locked` | Concurrent write operations from ingestion daemons while UI reads. | UI 500 error or crash. | 1. Enforce `PRAGMA journal_mode = WAL;`<br>2. Set `PRAGMA busy_timeout = 5000;`<br>3. Use short scoped connection context managers. |
| Path separator mismatch (`\` vs `/`) | Windows backslashes in `G:\My Drive` passed unescaped to frontend URLs. | 404 proxy load errors. | Gateway normalizes local filesystem paths into web-safe proxy URLs (e.g. `/proxies/VID_001_proxy.mp4`) or encoded URI format. |
| Memory exhaustion from large media lists | Rendering 1000 `<video>` DOM nodes simultaneously in jsdom or browser. | Heap blowout, slow test execution. | Implement virtualization / lazy loading in `MediaGallery` and mock video loading in test setup. |
| Ghost Media / Foreign Key Orphanage | Deleting an album leaves orphaned media rows in SQLite. | Database integrity corruption. | Enforce `PRAGMA foreign_keys = ON;` and `ON DELETE CASCADE` on `media.album_id`. |
| Double submission on Grading Trigger | User clicks "Grade Selected" multiple times during API latency. | Duplicate background ML jobs. | Disable button immediately upon initial click and manage `isSubmitting` state. |
| Destructive SQL / File deletion in tests | Accidental `DROP TABLE` or `os.remove` in automated test paths. | Workspace pollution / Rule R2 violation. | Enforce AST static guardrails and `tmp_path` fixture sandboxing. |

---

## 7. Implementation Blueprint for Downstream Agents

1. **Database Module (`gateway/media_catalog.py` & `gateway/schema_media_catalog.sql`)**:
   - Write SQL DDL with `albums` and `media` tables, check constraints, indexes, WAL mode.
   - Implement `MediaCatalog` database manager class with `init_db()`, `create_album()`, `add_media_batch()`, `get_albums_with_media()`, `update_grading_result()`.
2. **Gateway Endpoints (`gateway/app.py`)**:
   - `GET /api/v1/gallery/albums`: Returns albums with nested media items.
   - `POST /api/v1/gallery/albums`: Creates a new album.
   - `POST /api/v1/gallery/media`: Ingests media items.
   - `POST /api/v1/ml/grade-batch`: Accepts `{"media_ids": string[]}` and triggers grading.
3. **Frontend Component & API Client (`dashboard/src/components/MediaGallery/` & `dashboard/src/lib/api.ts`)**:
   - Implement `MediaGallery.tsx`, `AlbumSection.tsx`, `MediaCard.tsx`, `GradingActionBar.tsx`.
   - Add `fetchGalleryAlbums()` and `gradeMediaBatch(mediaIds)` to `src/lib/api.ts`.
4. **Automated Test Suites**:
   - Backend: `tests/test_media_catalog_db.py` & `tests/test_media_gallery_api.py`.
   - Frontend: `dashboard/__tests__/media-gallery.test.tsx`.
