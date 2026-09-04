# Omnichannel Triage Hub — Architectural Survey & UI Specification

## 1. Executive Summary & Source Artifact Location

This survey analyzes the design, structure, styling, and interactive behaviors defined in `triage_ui_mockup.html` to establish the foundational blueprint for the **Omnichannel Triage Hub** application (`React + Vite + Tailwind CSS + FastAPI + Firebase Data Connect`).

- **Mockup Source Location**: `c:\Users\noahp\.gemini\antigravity\brain\03e850e0-303c-44ee-aa25-0cc709bfba8b\triage_ui_mockup.html`
- **Mockup Metadata**: Full-screen triage interface with comprehension cues, live phone link monitoring, and deduplication collision resolution.
- **Target Workspace Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\omnichannel_triage_hub\`

---

## 2. Layout & Visual Design System

### 2.1 Color Tokens & CSS Variables
The UI is styled using a modern, dark-mode first design system relying on standard CSS variable tokens:

| Token | CSS Variable | Recommended Tailwind / Hex Equivalent | Role |
|---|---|---|---|
| Background | `var(--background)` | `#09090b` (`zinc-950` / `#0B0F17`) | Global page backdrop |
| Foreground | `var(--foreground)` | `#f8fafc` (`slate-50` / `#FFFFFF`) | Primary body and header text |
| Card Surface | `var(--card)` | `#18181b` (`zinc-900` / `#111827`) | Panel container surfaces |
| Border | `var(--border)` | `rgba(255, 255, 255, 0.1)` (`zinc-800` / `slate-800`) | Card and header dividing lines |
| Primary Accent | `var(--primary)` | `#3b82f6` (`blue-500`) or `#6366f1` (`indigo-500`) | Active badges, highlights, focus rings |
| Muted Foreground | `var(--muted-foreground)` | `#94a3b8` (`slate-400` / `zinc-400`) | Subtitles, labels, secondary metadata |
| ADB Success / Local Accent | `green-500` / `green-400` | `#22c55e` / `#4ade80` | Local ADB pulls, successful sync indicators |
| Takeout Cloud / Conflict Accent | `red-500` / `red-400` | `#ef4444` / `#f87171` | Takeout compressed copies, live ping status |
| Conflict Warning Accent | `amber-500` / `amber-400` | `#f59e0b` / `#fbbf24` | Resolution mismatch badges |

### 2.2 Global Layout Constraints
- **Container Structure**: `h-screen overflow-hidden flex flex-col p-8 bg-[var(--background)] text-[var(--foreground)] antialiased`
- **Main Grid**: `grid grid-cols-12 gap-8 flex-1 overflow-hidden`
  - **Left Column (Stream & Vision)**: `col-span-4 flex flex-col overflow-hidden`
  - **Right Column (Deduplication & Queue)**: `col-span-8 flex flex-col space-y-8 overflow-hidden`
- **Scrollbar Styling**:
  - Width/Height: `8px`
  - Track: `transparent`
  - Thumb: `var(--border)` with `border-radius: 4px`
  - Hover: `var(--muted-foreground)`

---

## 3. UI Component Hierarchy & Detailed Specifications

```
App.tsx
 ├── Header.tsx (Master Control & Status Badges)
 │    ├── Title & Subtitle
 │    ├── AdbStatusBadge.tsx (Live Pulse, Progress in GB)
 │    └── PhoneLinkStatusBadge.tsx (Live Pulse, Capture State)
 └── MainWorkspace.tsx (12-Column Grid)
      ├── PhoneLinkFeed.tsx (Left Column - 4 cols)
      │    ├── PanelHeader.tsx (Title, "Ctrl+Shift+T to Tag" Hotkey Badge, Description)
      │    ├── LiveFeedMockup.tsx (9:16 aspect ratio phone canvas, live capture ping)
      │    └── VisionResultCard.tsx (Entity L2, Attribute L3, Action confirmation)
      └── CollisionArena.tsx (Right Column - 8 cols)
           ├── ArenaHeader.tsx (Collision Resolution Queue header & context explainer)
           └── CollisionList.tsx (Scrollable collision items)
                └── CollisionCard.tsx (Individual conflict resolution card)
                     ├── CardHeader.tsx (Filename tag, UTC Timestamp, Warning badge)
                     ├── ComparisonGrid.tsx (2-column side-by-side)
                     │    ├── SourceComparisonBox.tsx [Local ADB: 4K 2160p, 538MB, Green ring]
                     │    └── SourceComparisonBox.tsx [Takeout: 1080p, 42MB, Red ring, opacity]
                     └── ActionButtons.tsx ("Keep 4K ADB Version (Auto-Trash Takeout)")
```

### 3.1 Header Component (`Header.tsx`)
- **Container**: `flex justify-between items-end mb-8 pb-4 border-b border-[var(--border)]`
- **Left Details**:
  - `<h1>`: `text-3xl font-bold tracking-tight mb-2` ("Omnichannel Triage Hub")
  - `<p>`: `text-[var(--muted-foreground)]` ("Visually verifying ADB, Google Takeout, and Live Phone Link streams.")
- **Right Status Badges**:
  - `flex space-x-6`
  - **ADB Status Badge**:
    - Title: `text-xs uppercase tracking-wider text-[var(--muted-foreground)] mb-1` ("ADB CONNECTION")
    - Pill: `flex items-center space-x-2 bg-green-500/10 text-green-500 px-3 py-1 rounded-full border border-green-500/20`
    - Indicator: `w-2 h-2 rounded-full bg-green-500 animate-pulse`
    - Content: Dynamic string (e.g. `Pulling (24.1 GB / 90.5 GB)` or `Idle / Synced`)
  - **Phone Link Status Badge**:
    - Title: `text-xs uppercase tracking-wider text-[var(--muted-foreground)] mb-1` ("WINDOWS PHONE LINK")
    - Pill: `flex items-center space-x-2 bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full border border-blue-500/20`
    - Indicator: `w-2 h-2 rounded-full bg-blue-400 animate-pulse`
    - Content: `Live Screen Capture Active`

### 3.2 Phone Link Feed (`PhoneLinkFeed.tsx` — Left Column: 4 Columns)
- **Container**: `col-span-4 flex flex-col bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-sm overflow-hidden relative`
- **Panel Header**:
  - `p-5 border-b border-[var(--border)] bg-black/20`
  - Title: `font-bold text-xl flex items-center justify-between` ("Phone Link Feed")
  - Hotkey Badge: `<span className="text-[10px] bg-[var(--primary)] text-white px-2 py-1 rounded uppercase tracking-wide">Ctrl+Shift+T to Tag</span>`
  - Explainer: `text-sm text-[var(--muted-foreground)] mt-2 leading-relaxed`
- **Panel Body**:
  - `flex-1 p-5 overflow-y-auto bg-black/40`
  - **Feed Stream Frame**:
    - `border border-[var(--primary)] rounded-xl overflow-hidden relative mb-4`
    - Live Indicator Overlay: `absolute top-2 right-2 bg-red-500 text-white text-xs px-2 py-1 rounded font-bold uppercase tracking-wider shadow-lg flex items-center` with `w-2 h-2 bg-white rounded-full animate-ping mr-2`
    - Phone Aspect Canvas: `aspect-[9/16] bg-gray-900 w-full flex flex-col items-center justify-center p-4`
    - Dashed Container: `w-full h-full bg-gray-800 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-700`
    - Mock Info: `[ Phone Link Stream ]` `Playing: 20260819_213606.mp4` `(Excision Drop)`
  - **Gemini Vision Analysis Box**:
    - `bg-[var(--background)] border border-[var(--border)] rounded-lg p-4`
    - Title: `text-sm font-bold text-[var(--primary)] mb-2` ("Gemini Vision Result")
    - Key-Value List (`text-sm space-y-2`):
      - **Entity (L2)**: `Excision`
      - **Attribute (L3)**: `Lasers, Bass Drop`
      - **Action**: `<span class="text-green-500">ADB Pull Triggered</span>`

### 3.3 Deduplication & Bulk Tagging Arena (`CollisionArena.tsx` — Right Column: 8 Columns)
- **Container**: `col-span-8 flex flex-col space-y-8 overflow-hidden`
- **Deduplication Card**:
  - `bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 shadow-sm flex flex-col flex-1 overflow-hidden`
  - Header:
    - Title: `font-bold text-xl mb-2` ("Collision Resolution Queue")
    - Explainer: `text-sm text-[var(--muted-foreground)]` ("Why are you seeing this? The script found photos in your Samsung pull and Google Takeout that share the exact same UTC-adjusted timestamp (within 2 seconds)...")
  - Scrollable Queue: `flex-1 overflow-y-auto space-y-6 pr-4`
- **Collision Item Card (`CollisionCard.tsx`)**:
  - Card Box: `border border-[var(--border)] rounded-xl p-5 bg-[var(--background)]`
  - Item Top Bar: `flex justify-between items-center mb-4 border-b border-[var(--border)] pb-4`
    - Filename: `font-mono text-sm bg-gray-800 px-2 py-1 rounded inline-block`
    - Timestamp: `text-xs text-[var(--muted-foreground)] ml-2` ("Taken: Aug 19, 2026 • 9:36 PM EST")
    - Warning Pill: `flex items-center text-xs text-amber-500 font-bold bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20` with alert SVG and text `Resolution Mismatch`
  - 2-Column Comparison Grid: `grid grid-cols-2 gap-6 mb-4`
    - **Local ADB Option**:
      - Box: `border-2 border-green-500/40 rounded-lg p-4 bg-green-900/10 relative`
      - Badge: `absolute -top-3 left-4 bg-green-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shadow` ("Local ADB Pull")
      - Content: Resolution `4K 2160p`, Path `Source: /sdcard/DCIM/Camera`, Size `538 MB`
    - **Takeout Cloud Option**:
      - Box: `border-2 border-red-500/40 rounded-lg p-4 bg-red-900/10 relative opacity-75 hover:opacity-100 transition-opacity`
      - Badge: `absolute -top-3 left-4 bg-red-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shadow` ("Takeout Cloud")
      - Content: Resolution `1080p Compressed`, Path `Source: Takeout/Google Photos`, Size `42 MB`
  - Action Row:
    - `flex space-x-3 mt-5`
    - Primary Button: `flex-1 bg-green-600 hover:bg-green-500 text-white py-3 rounded-lg font-bold shadow-lg transition-all transform hover:scale-[1.02]` ("Keep 4K ADB Version (Auto-Trash Takeout)")

---

## 4. State Management & Interaction Architecture

### 4.1 React State Model
1. **`adbStatus`**:
   - Status: `'idle' | 'pulling' | 'completed' | 'error'`
   - Progress: `{ pulledBytes: number, totalBytes: number, currentFile: string }`
2. **`phoneLinkStream`**:
   - Status: `'active' | 'paused' | 'analyzing'`
   - Active Video: `{ filename: string, track: string, previewUrl?: string }`
   - Vision Result: `{ entity: string, attributes: string[], actionStatus: string }`
3. **`collisionQueue`**:
   - List of unresolved collisions:
     ```typescript
     interface CollisionItem {
       id: string;
       filename: string;
       timestampFormatted: string;
       conflictType: 'Resolution Mismatch' | 'Duplicate Hash';
       adbSource: {
         resolution: string;
         resolutionSubtext: string;
         sourcePath: string;
         size: string;
       };
       takeoutSource: {
         resolution: string;
         resolutionSubtext: string;
         sourcePath: string;
         size: string;
       };
     }
     ```
4. **Interactive Handlers**:
   - `handleResolveCollision(id: string, choice: 'adb' | 'takeout')`: Optimistically removes item from queue, triggers API/DataConnect mutation.
   - `handleTriggerAdbPull()`: Dispatches POST request to FastAPI daemon `POST http://localhost:8000/api/trigger-adb-pull`.
   - `handleCaptureScreen()` / `Ctrl+Shift+T` hotkey: Listens for keyboard combination globally and posts to `POST http://localhost:8000/api/capture-screen`.

---

## 5. Backend FastAPI Daemon Contract (`local_daemon/main.py`)

To satisfy Requirement R2 and the acceptance criteria, the FastAPI service on `localhost:8000` requires:

1. **CORS Middleware**: Configured to allow `http://localhost:5173` (Vite dev server) with all methods and headers.
2. **Endpoints**:
   - `GET /health` or `GET /api/status`: Returns current daemon status, ADB connection state, and Phone Link window hook status.
   - `POST /api/trigger-adb-pull`: Initiates ADB pull or returns simulated/actual pull progress.
     - Response: `{"status": "success", "message": "ADB Pull started", "details": {...}}`
   - `POST /api/capture-screen`: Triggers screen capture of Phone Link window and runs Gemini Vision tagging.
     - Response: `{"status": "success", "entity": "Excision", "attributes": ["Lasers", "Bass Drop"], "action": "ADB Pull Triggered"}`

---

## 6. Firebase Data Connect Schema & Client SDK Setup

To satisfy Requirement R3, Firebase Data Connect requires:

1. **Schema Definition (`dataconnect/schema/schema.gql`)**:
   ```graphql
   type VideoTag @table(name: "video_tags", key: "id", singular: "videoTag", plural: "videoTags") {
     id: Int64! @default(expr: "autoIncrement()")
     filename: String! @unique
     filepath: String!
     domain: String! @default(value: "Unknown")
     entity: String! @default(value: "Unknown")
     viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb") @default(value: [])
     technical: Any! @col(name: "technical", dataType: "jsonb") @default(value: {})
     createdAt: Timestamp! @col(name: "created_at") @default(expr: "request.time")
     updatedAt: Timestamp! @col(name: "updated_at") @default(expr: "request.time")
   }
   ```
2. **Connector Queries (`dataconnect/connector/queries.gql`)**:
   ```graphql
   query ListVideoTags @auth(level: PUBLIC) {
     videoTags {
       id
       filename
       filepath
       domain
       entity
       viralFeatures
       technical
       createdAt
     }
   }
   ```
3. **SDK Generation (`dataconnect/connector/connector.yaml`)**:
   Target output directory: `../frontend/src/lib/dataconnect` with package `@firebase/data-connect`.

---

## 7. Quality & Zero-Waste Verification Plan (R4)

To guarantee compliance with rule `R4`:
1. **Accessibility (`a11y-debugging`)**:
   - Ensure all interactive elements have semantic buttons, valid ARIA labels (`aria-label`), and sufficient color contrast against dark backgrounds.
   - Hotkey notification (`Ctrl+Shift+T`) is supplemented with an accessible screen-reader announcement.
2. **Memory Leak Audit (`memory-leak-debugging`)**:
   - Verify unmounting components properly clean up `window.addEventListener('keydown')` event listeners and interval polling timers.
   - Zero detached DOM nodes in React tree.
3. **LCP & Performance (`debug-optimize-lcp`)**:
   - Ensure CSS variable definitions load instantly without layout shifts.
   - Vite build bundle optimization.
