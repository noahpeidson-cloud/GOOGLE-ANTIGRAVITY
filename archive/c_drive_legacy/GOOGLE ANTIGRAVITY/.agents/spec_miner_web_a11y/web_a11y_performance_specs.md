# Web Frontend Architecture, Accessibility (a11y), and Performance Specification

**Author:** Specification Miner (Frontend Architect & a11y/Performance Specialist)  
**Date:** 2026-08-22  
**Status:** Approved Standard / Mandatory Implementation Specification  
**Scope:** Antigravity Ecosystem Web Frontends (`apps/`, `content_creation/`, Chrome Extensions, Mobile Webviews, PWA Dashboards)  
**Conformance Standard:** WCAG 2.1 Level AA, Section 508, W3C Web Content Accessibility Guidelines, Core Web Vitals (CWV) Standards

---

## 1. Executive Summary & Specification Scope

This specification establishes the mandatory engineering standards, architectural constraints, accessibility rules, and automated CI/CD verification testing gates across all user-facing web applications within the Google Antigravity ecosystem. 

All production frontend deliverables—including the EDM Master Dashboard PWA, Chrome Extension interfaces, React/Vite client applications, and embedded webviews—must adhere strictly to the rules codified herein. Compliance is verified mechanically through automated testing gates (axe-core, Lighthouse CI, Pa11y, and Playwright performance traces) before merging or deployment.

---

## 2. Features Discovered & Mined Capabilities

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | UI Architecture | Component-Driven Isolation | Modular, encapsulated component boundaries using Web Components or React/Vite with strict prop interfaces | Component props, design tokens, slots | Rendered DOM subtree, emitted custom events | Throws inside React Error Boundary / Fallback UI rendered | `apps/GEMINI.md`, `modern-web-guidance` |
| 2 | UI Architecture | Native Popover & Dialog Top Layer | Native `<dialog>` and `popover="manual"` overlays for modal workflows and persistent toasts | User trigger, backdrop click, Escape key | Top-layer rendered overlay with automatic stacking | Trapped focus on dialog open, light dismiss fallback | `modern-web-guidance` (`html`, `persistent-toast-notifications`) |
| 3 | UI Architecture | View Transitions API | Hardware-accelerated seamless page and state morphing animations | DOM mutation callback passed to `document.startViewTransition()` | Coordinated pseudo-element CSS animation | Degrades gracefully without animation on older browsers or `prefers-reduced-motion` | `content_creation/index.html`, `modern-web-guidance` |
| 4 | Offline / PWA | Service Worker Cache Strategies | Service worker lifecycle handling Cache-First for static assets, Network-First for API data, Stale-While-Revalidate for proxies | HTTP Fetch events, CacheStorage | Cached Response object or network fetch | Emits offline fallback response or status 503 error artifact | `ORIGINAL_REQUEST.md`, `modern-web-guidance` |
| 5 | State & Storage | Resilient Optimistic State Engine | Instant UI updates for timeline slicing and pipeline triggering with automated rollback on API error | Action dispatch, API Promise | Optimistic state commit, DOM re-render | Catches API rejection, rolls back state, displays error toast | `apps/GEMINI.md`, `content_creation/index.html` |
| 6 | State & Storage | Secure IndexedDB Storage | Asynchronous client-side metadata and asset proxy caching using IndexedDB and Web Crypto API | Structured JSON, Binary Blobs | Persisted records with schema versioning | Handles `onversionchange`, `onblocked`, and quota exceeded | `apps/GEMINI.md` |
| 7 | a11y: Semantics | Semantic Landmark & Heading Matrix | Native HTML5 landmark hierarchy (`<main>`, `<nav>`, `<aside>`, `<header>`, `<footer`) with unskipped `<h1>`-`<h6>` | HTML structure | Accessible Tree landmark nodes | Fails automated Lighthouse a11y and axe audit if skipped | `a11y-debugging` (`SKILL.md`) |
| 8 | a11y: ARIA | Live Region Announcement Protocols | Screen reader announcement of background job status and pipeline errors via `aria-live="polite"` and `role="alert"` | Dynamic status string, severity level | Synthesized voice notification to assistive tech | Suppresses notification if element is destroyed before announcement | `a11y-debugging` (`references/a11y-snippets.md`) |
| 9 | a11y: Keyboard | Focus Trapping & Restoration Engine | Trapping Tab focus within active modal dialogs and restoring focus to the origin trigger element upon dismissal | Keyboard Tab / Shift+Tab, Escape key | Managed DOM focus state on interactive elements | Prevents focus escape to background `inert` elements | `a11y-debugging`, `modern-web-guidance` |
| 10 | a11y: Touch | 48x48px Minimum Tap Target Enforcement | Bounding box minimum touch area constraint with >= 8px inter-target spacing | CSS dimensions, padding, margins | Touch hit target >= 48x48 CSS pixels | Triggers layout linter warning / axe-core failure | `a11y-debugging` (`references/a11y-snippets.md`) |
| 11 | a11y: Contrast | WCAG AA Contrast Ratios | Minimum color contrast of 4.5:1 for normal text and 3:1 for large text / graphical UI borders | Foreground RGB, Background RGB | Calculated relative luminance contrast ratio | Fails CI build if contrast ratio < 4.5:1 (normal) or < 3.0:1 (large) | `a11y-debugging`, WCAG 2.1 AA |
| 12 | CWV: LCP | LCP Subpart Optimization Pipeline | Engineering LCP to < 2.5s: TTFB < 1000ms, Resource Delay < 250ms, Load Duration < 1000ms, Render Delay < 250ms | Hero asset URL, preload tags, `fetchpriority` | Fast render of primary visual hero in viewport | Triggers CI performance failure if LCP > 2.5s | `debug-optimize-lcp` (`SKILL.md`) |
| 13 | CWV: LCP | High-Priority Asset Discovery | Explicit `fetchpriority="high"`, `<link rel="preload">`, and preconnect directives for critical hero assets | HTML `<link>` and `<img>` attributes | Immediate prioritized browser network scheduling | Prevents browser network delay bottlenecks | `debug-optimize-lcp`, `modern-web-guidance` |
| 14 | CWV: INP | Interaction-to-Next-Paint Optimization | INP latency budget < 200ms using `scheduler.yield()`, Long Animation Frames (LoAF) monitoring, and Web Workers | User click, keypress, or drag event | UI frame rendering < 200ms | Surfaces LoAF warning if task execution > 50ms | `modern-web-guidance` (`identify-inp-causes`) |
| 15 | CWV: CLS | Cumulative Layout Shift Stabilization | Enforcing CLS < 0.1 via explicit `aspect-ratio`, reserved skeleton dimensions, and font fallback matching | Image/video width & height attributes, CSS | Zero unexpected layout shifts during load | Fails Lighthouse CI if CLS score >= 0.1 | `modern-web-guidance` (`performance`) |
| 16 | Asset Pipeline | Modern AVIF/WebP Compression | Next-generation image format negotiation with fallback `srcset` and Brotli asset compression | Raw image/media buffers | Highly compressed media payload | Falls back to WebP / JPEG if client lacks AVIF support | `modern-web-guidance` (`performance`) |
| 17 | CI/CD Gates | Automated axe-core & Lighthouse a11y | Headless browser execution enforcing Lighthouse a11y score >= 95 and zero critical axe violations | PR build trigger, deployed staging URL | Automated test report & pass/fail status | Blocks PR merge on violations | `ORIGINAL_REQUEST.md`, CI/CD standards |
| 18 | CI/CD Gates | Automated Lighthouse Performance Budget | Headless Lighthouse CI run enforcing Performance score >= 90 and LCP < 2.5s under 4x CPU / 3G throttling | PR build trigger, staging URL | Audit report artifact with subpart breakdown | Fails build if performance score < 90 | `ORIGINAL_REQUEST.md`, `debug-optimize-lcp` |

---

## 3. Edge Cases & Observed Failure Modes

| # | Feature | Input / Trigger | Observed Behavior | Remediation / Mandated Guardrail |
|---|---|---|---|---|
| 1 | Modal Dialog Focus | User opens `<dialog>` while background content has tabindex elements | Screen readers can read background DOM elements; keyboard focus escapes dialog | Background elements MUST receive `inert` attribute; dialog must call `.showModal()` instead of `.show()` |
| 2 | LCP Hero Image | Image tag has `loading="lazy"` while positioned in initial top viewport | Browser delays fetching hero image until layout calculation completes, adding 1.5s+ to LCP | NEVER add `loading="lazy"` to viewport elements. Viewport hero images MUST have `fetchpriority="high"` |
| 3 | Safe Zone HUD Overlays | YouTube Shorts (900x1270) & TikTok (920x1310) HUD overlays rendered over video canvas | Overlay clicks block scrub events on underlying proxy canvas | Overlays MUST set `pointer-events: none` on frame containers and `pointer-events: auto` only on controls |
| 4 | Offline Sync Recovery | Network disconnects while user adjusts video trim points in PWA | `POST /trigger-pipeline` fails with NetworkError; user edits lost | Edits cached to IndexedDB queue; Service Worker Background Sync triggers replay on `navigator.onLine` |
| 5 | Color Contrast in Dark Mode | Subdued secondary metadata text `#64748B` rendered on base canvas `#0B0F19` | Contrast ratio is 2.8:1, failing WCAG AA minimum 4.5:1 | Secondary text MUST use token `--color-text-secondary: #94A3B8` (contrast ratio 6.2:1 against `#0B0F19`) |
| 6 | Touch Target on Timeline | Timeline scrub head width set to 12px for desktop precision | Touch users on mobile cannot reliably grab scrub playhead | Implement invisible touch wrapper with `min-width: 48px; min-height: 48px;` around visual 12px playhead |
| 7 | Custom Font Swap CLS | Custom web font loads late and swaps with system fallback font | Font metric mismatch causes text re-flow and layout shift (CLS spike > 0.15) | Use `font-display: swap` paired with CSS `@font-face` metric overrides: `ascent-override`, `descent-override`, `size-adjust` |
| 8 | Large Long Tasks on UI Thread | Video waveform rendering script processes 5MB audio buffer synchronously | Main thread blocked for 350ms, causing INP failure (> 300ms) on user drag | Offload audio decoding/waveform peak calculation to a dedicated `Worker()`; yield main thread via `scheduler.yield()` |
| 9 | Toast Notification Spam | Fast sequential background tasks emit multiple `aria-live="assertive"` toasts | Screen reader cuts off previous announcement, confusing user | Non-critical updates MUST use `aria-live="polite"` with queue throttling. Only critical errors use `role="alert"` |
| 10 | Dynamic Form Invalidation | User submits invalid form; errors displayed visually in red text | Screen reader user receives no auditory feedback of errors | Inputs MUST set `aria-invalid="true"` and `aria-errormessage="error-id"`, with focus shifted to first invalid field |

---

## 4. Section 1: Modern Web Guidance & UI Architecture

### 4.1 Component-Driven Design & State Management
1. **Encapsulation**: Components must be decoupled, single-responsibility units. CSS must use CSS Modules, scoped custom properties (`--component-state`), or Shadow DOM to prevent style leakage.
2. **Prop Validation & Types**: Strict TypeScript interfaces are mandatory for all props, states, and event payloads. No `any` types permitted.
3. **State Architecture**:
   - **Local State**: Component-scoped transient states (hover, open/closed menus, input focus).
   - **Application State**: Global state stores (Zustand, Redux Toolkit, or lightweight native EventTarget stores) for multi-pane sync (e.g. proxy metadata, render queue, active clip).
   - **Optimistic UI Engine**: High-frequency user interactions (e.g. trim mark adjustment, queue reordering) must update the DOM immediately. An asynchronous mutation rollback handler must revert state and alert the user if the backend returns an error:
     ```typescript
     async function executeOptimisticUpdate<T>(
       optimisticState: T,
       applyState: (s: T) => void,
       revertState: () => void,
       apiCall: () => Promise<void>
     ): Promise<void> {
       applyState(optimisticState);
       try {
         await apiCall();
       } catch (error) {
         revertState();
         toastNotification.show({
           type: 'error',
           message: 'Action failed. Changes have been reverted.',
           ariaLive: 'assertive'
         });
       }
     }
     ```
4. **Resilient Error Boundaries**: All major multi-pane layout sections (Sidebar, Canvas, Inspector, Timeline) must be wrapped in isolated React Error Boundaries or native unhandled-rejection listeners. A crash in one panel (e.g. canvas WebGL failure) must not crash the surrounding dashboard.

### 4.2 Responsive & Adaptive Layout Systems
1. **Modern CSS Grid & Dockable Panes**: Desktop-first multi-pane layouts must use CSS Grid with defined grid-template-areas, falling back to responsive stacked flex layouts on viewports `< 1024px`:
   ```css
   .app-grid-container {
     display: grid;
     grid-template-columns: var(--sidebar-left-width, 320px) 1fr var(--sidebar-right-width, 340px);
     grid-template-rows: var(--topbar-height, 52px) 1fr var(--timeline-height, 270px) var(--footer-height, 32px);
     grid-template-areas:
       "topbar topbar topbar"
       "sidebar-left canvas sidebar-right"
       "timeline timeline timeline"
       "footer footer footer";
     height: 100dvh;
     overflow: hidden;
   }

   @media (max-width: 1023px) {
     .app-grid-container {
       grid-template-columns: 1fr;
       grid-template-rows: auto;
       grid-template-areas:
         "topbar"
         "canvas"
         "timeline"
         "sidebar-left"
         "sidebar-right"
         "footer";
       overflow-y: auto;
     }
   }
   ```
2. **Container Queries (`@container`)**: Reusable components (such as proxy preview cards or metadata inspectors) must adapt their typography and spacing based on container width rather than viewport width:
   ```css
   .inspector-panel {
     container-type: inline-size;
     container-name: inspector;
   }

   @container inspector (max-width: 300px) {
     .metadata-grid {
       grid-template-columns: 1fr;
     }
   }
   ```

### 4.3 Progressive Enhancement & PWA Integration
1. **Progressive Enhancement**: All core workflows must remain functional without JavaScript where feasible (semantic forms, native links). High-level features (View Transitions, Web Workers, IndexedDB) must be feature-detected:
   ```javascript
   if (document.startViewTransition) {
     document.startViewTransition(() => updateDOM(state));
   } else {
     updateDOM(state);
   }
   ```
2. **Web App Manifest V3**: PWAs must provide a valid `manifest.json` specifying `display: "standalone"`, `theme_color`, `background_color`, and crisp icon assets (192x192, 512x512, maskable).
3. **Service Worker Architecture**:
   - **Static Assets (HTML/CSS/JS/WASM)**: Cache-First strategy with hash-versioned filenames.
   - **API Status / Health (`/status`, `/health`)**: Network-First strategy with 3-second timeout fallback.
   - **Video Proxies (`/proxies/*`)**: Stale-While-Revalidate with IndexedDB blob chunk caching.

### 4.4 Secure Client-Side Storage
1. **Storage Separation**:
   - **Sensitive Auth Tokens / Keys**: Never store sensitive long-lived keys in `localStorage` or `sessionStorage` (vulnerable to XSS). Use secure, HttpOnly, SameSite=Strict cookies.
   - **Local Application State / Drafts**: Store in `IndexedDB` with schema versioning via the `idb` wrapper.
   - **Transient UI State**: Store in `sessionStorage` (e.g. active tab index).
2. **Content Security Policy (CSP)**: All web pages must include strict CSP headers:
   ```http
   Content-Security-Policy: default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' ws: wss:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self';
   ```

---

## 5. Section 2: Strict Accessibility (a11y) Standards & Rules

### 5.1 WCAG 2.1 Level AA & Section 508 Conformance Matrix

| WCAG Criterion | Level | Description | Implementation Requirement |
|---|---|---|---|
| 1.1.1 Non-text Content | A | All non-text content has text alternative | Meaningful `alt` on informative images; `alt=""` or `aria-hidden="true"` on decorative icons |
| 1.3.1 Info and Relationships | A | Information, structure, and relationships conveyed programmatically | Semantic HTML5 elements (`<header>`, `<nav>`, `<main>`, `<section>`, `<h1>`-`<h6>`, `<fieldset>`, `<legend>`) |
| 1.4.3 Contrast (Minimum) | AA | Normal text >= 4.5:1; Large text >= 3:1 | All text tokens verified by color luminance formula; automated axe CI gates |
| 1.4.11 Non-text Contrast | AA | UI components & graphical objects >= 3:1 | Input borders, focus rings, status badges, active tab markers >= 3:1 against adjacent background |
| 2.1.1 Keyboard | A | All functionality operable via keyboard | Full keyboard accessibility without mouse requirement; custom widgets use roving tabindex |
| 2.1.2 No Keyboard Trap | A | Keyboard focus can be moved away from any component | Focus trap inside modals must be released upon Escape or modal close |
| 2.4.1 Bypass Blocks | A | Mechanism to bypass repeated content | Top-of-page `<a href="#main-content" class="skip-link">Skip to main content</a>` |
| 2.4.3 Focus Order | A | Focusable components receive focus in logical order | DOM order matches visual reading order; no absolute positioning hacks altering logical flow |
| 2.4.7 Focus Visible | AA | Keyboard focus indicator is visible | Custom high-contrast `:focus-visible` outline: `outline: 2px solid #3B82F6; outline-offset: 2px;` |
| 2.5.5 Target Size | AAA (Enforced AA) | Minimum touch target 48x48px | All clickable buttons, scrub heads, and icons have at least 48x48px interactive bounding box |
| 4.1.2 Name, Role, Value | A | UI components have accessible name and role | Inputs have associated `<label for="...">`; buttons have descriptive text or `aria-label` |
| 4.1.3 Status Messages | AA | Status updates presented to assistive technologies | Dynamic status/alert toasts use `role="status"` (`aria-live="polite"`) or `role="alert"` (`aria-live="assertive"`) |

### 5.2 Semantic HTML Structure & Landmarks
1. **Document Outline**: Every page must have a single `<h1>` representing the page title, followed by strictly hierarchical `<h2>`-`<h6>` headers without skipping levels (e.g. `<h1>` -> `<h2>` -> `<h3>`, never `<h1>` -> `<h3>`).
2. **Landmarks**:
   ```html
   <header role="banner">
     <nav role="navigation" aria-label="Main Navigation">...</nav>
   </header>
   <main id="main-content" role="main">
     <section aria-labelledby="proxy-viewer-title">
       <h2 id="proxy-viewer-title" class="sr-only">720p Proxy Viewer</h2>
       <!-- Viewer components -->
     </section>
     <section aria-labelledby="timeline-title">
       <h2 id="timeline-title" class="sr-only">Audio & Video Timeline</h2>
       <!-- Timeline tracks -->
     </section>
   </main>
   <aside role="complementary" aria-label="Metadata Inspector">...</aside>
   <footer role="contentinfo">...</footer>
   ```
3. **Screen Reader Only Utility Class (`.sr-only`)**:
   ```css
   .sr-only {
     position: absolute !important;
     width: 1px !important;
     height: 1px !important;
     padding: 0 !important;
     margin: -1px !important;
     overflow: hidden !important;
     clip: rect(0, 0, 0, 0) !important;
     white-space: nowrap !important;
     border: 0 !important;
   }
   ```

### 5.3 ARIA Roles, States, and Focus Management
1. **Native over ARIA**: Always use native HTML elements (`<button>`, `<dialog>`, `<input>`, `<select>`) before custom ARIA roles.
2. **Modal Dialog Focus Trap Pattern**:
   ```javascript
   function trapFocus(modalElement) {
     const focusableElements = modalElement.querySelectorAll(
       'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
     );
     const firstFocusable = focusableElements[0];
     const lastFocusable = focusableElements[focusableElements.length - 1];

     modalElement.addEventListener('keydown', (e) => {
       if (e.key === 'Tab') {
         if (e.shiftKey && document.activeElement === firstFocusable) {
           lastFocusable.focus();
           e.preventDefault();
         } else if (!e.shiftKey && document.activeElement === lastFocusable) {
           firstFocusable.focus();
           e.preventDefault();
         }
       }
       if (e.key === 'Escape') {
         closeModal(modalElement);
       }
     });
   }
   ```
3. **Skip Navigation Links**:
   ```html
   <a href="#main-content" class="skip-link">Skip to main content</a>
   ```
   ```css
   .skip-link {
     position: absolute;
     top: -999px;
     left: 1rem;
     background: #3B82F6;
     color: #FFFFFF;
     padding: 0.75rem 1.5rem;
     z-index: 10000;
     font-weight: 600;
     border-radius: 4px;
     transition: top 0.2s ease-in-out;
   }
   .skip-link:focus {
     top: 1rem;
     outline: 3px solid #FFFFFF;
   }
   ```

### 5.4 Tap Targets & Contrast Rules
1. **Tap Targets**: All buttons, links, and touch-interactive handles must have minimum dimensions of 48x48 CSS pixels. When visual appearance requires a smaller icon (e.g. 24px icon), use padding or pseudo-elements to expand the touch boundary:
   ```css
   .icon-button {
     position: relative;
     width: 24px;
     height: 24px;
     padding: 0;
     border: none;
     background: transparent;
   }
   .icon-button::after {
     content: '';
     position: absolute;
     top: 50%;
     left: 50%;
     transform: translate(-50%, -50%);
     width: 48px;
     height: 48px;
   }
   ```
2. **Color Contrast Tokens**:
   - Primary Text (`#E2E8F0`) on Base Background (`#0B0F19`): **14.8:1** (Passes AAA)
   - Secondary Text (`#94A3B8`) on Base Background (`#0B0F19`): **6.2:1** (Passes AA)
   - Active Electric Blue Accent (`#3B82F6`) on Elevated Panel (`#1A2234`): **4.5:1** (Passes AA)
   - Warning Amber (`#F59E0B`) on Elevated Panel (`#1A2234`): **6.8:1** (Passes AA)

---

## 6. Section 3: Web Performance & Core Web Vitals Optimization

### 6.1 Largest Contentful Paint (LCP) Budget & Engineering Protocol
**LCP Target**: **< 2.5 seconds** on real-world mobile networks (Fast 3G) and mid-tier mobile hardware (4x CPU slowdown).

```
+---------------------------------------------------------------------------------------+
|                                    TOTAL LCP BUDGET < 2500ms                          |
+---------------------------+-----------------------+-------------------+---------------+
| 1. Time to First Byte     | 2. Resource Load Delay| 3. Resource Load  | 4. Render     |
|    (TTFB): ~40% (1000ms)  |    (Delay): <10%(250ms)|    Duration: 40%  |    Delay: <10%|
|                           |                       |    (1000ms)       |    (250ms)    |
+---------------------------+-----------------------+-------------------+---------------+
```

#### LCP Subpart Optimization Rules:
1. **Subpart 1 — TTFB (< 1000ms)**:
   - Serve static HTML directly from Cloudflare / Cloud CDN edge nodes.
   - Enable HTTP/2 or HTTP/3 multiplexing and TLS 1.3 resumption.
   - Use aggressive cache-control headers on static assets (`Cache-Control: public, max-age=31536000, immutable`).
2. **Subpart 2 — Resource Load Delay (< 250ms)**:
   - Discoverability: The LCP asset (e.g. video poster image or hero logo) must exist in the raw HTML payload. Never inject the LCP element via runtime client-side JavaScript.
   - Priority Boost: Critical viewport images MUST include `fetchpriority="high"`.
   - Preload Directives:
     ```html
     <link rel="preconnect" href="https://storage.googleapis.com" crossorigin>
     <link rel="preload" as="image" href="/images/hero-poster.avif" type="image/avif" fetchpriority="high">
     ```
   - Anti-Pattern: NEVER put `loading="lazy"` on any element in the initial viewport.
3. **Subpart 3 — Resource Load Duration (< 1000ms)**:
   - Modern Formats: Images must be delivered in AVIF (preferred) or WebP format with automated dimension resizing via `<picture>` / `srcset`.
   - Payload Budget: LCP image file size must not exceed **150 KB**.
4. **Subpart 4 — Element Render Delay (< 250ms)**:
   - Inline Critical CSS: Extract and inline critical layout styles in `<head>`.
   - Defer Non-Critical Scripts: All JavaScript tags must use `type="module"` or `defer`. Synchronous `<script src="...">` tags in `<head>` are strictly forbidden.
   - Font Loading: Fonts must specify `font-display: swap` to prevent Flash of Invisible Text (FOIT).

### 6.2 Interaction to Next Paint (INP) Engineering (< 200ms)
1. **Long Task Elimination**: Any synchronous JavaScript execution exceeding 50ms blocks the main thread and degrades INP.
2. **Task Chunking with `scheduler.yield()`**: Break heavy loops (such as audio waveform parsing or proxy playlist indexing) into cooperative micro-tasks:
   ```javascript
   async function processWaveformData(buffer) {
     const chunkSize = 5000;
     for (let i = 0; i < buffer.length; i += chunkSize) {
       processChunk(buffer.slice(i, i + chunkSize));
       // Yield main thread back to the browser event loop
       if ('scheduler' in window && 'yield' in window.scheduler) {
         await window.scheduler.yield();
       } else {
         await new Promise((resolve) => setTimeout(resolve, 0));
       }
     }
   }
   ```
3. **Web Worker Offloading**: Heavy compute operations (FFmpeg metadata parsing, cryptographic hashing, waveform peak reduction) must run inside dedicated Web Workers.

### 6.3 Cumulative Layout Shift (CLS) Stabilization (< 0.1)
1. **Explicit Dimensions**: All `<img>`, `<video>`, `<canvas>`, and `<iframe>` elements must include explicit `width` and `height` attributes or CSS `aspect-ratio`:
   ```css
   .proxy-video-container {
     width: 100%;
     aspect-ratio: 16 / 9;
     background-color: var(--color-bg-surface-dark);
     contain: layout size;
   }
   ```
2. **Reserved Dynamic Insertion Slots**: Dynamic banners, render queue updates, and toasts must use pre-allocated containers with CSS `min-height` so insertions do not push surrounding content downward.
3. **Font Metric Overrides**: Custom web fonts must match system fallback metrics to eliminate shift on font swap:
   ```css
   @font-face {
     font-family: 'Inter Fallback';
     src: local('Arial');
     ascent-override: 90%;
     descent-override: 22%;
     line-gap-override: 0%;
     size-adjust: 107%;
   }
   ```

### 6.4 Asset Compression & Bundle Splitting
1. **Bundle Budget**:
   - Initial Entry JavaScript: **< 150 KB** (gzipped / brotli).
   - Initial Critical CSS: **< 30 KB** (inlined in `<head>`).
2. **Vite Bundle Splitting Configuration**:
   ```javascript
   // vite.config.ts
   import { defineConfig } from 'vite';

   export default defineConfig({
     build: {
       target: 'esnext',
       minify: 'esbuild',
       rollupOptions: {
         output: {
           manualChunks(id) {
             if (id.includes('node_modules')) {
               if (id.includes('react') || id.includes('react-dom')) {
                 return 'vendor-react';
               }
               if (id.includes('wavesurfer') || id.includes('tone')) {
                 return 'vendor-audio';
               }
               return 'vendor-core';
             }
           }
         }
       }
     }
   });
   ```

---

## 7. Section 4: Mandatory CI/CD Verification & Testing Gates

### 7.1 Automated CI/CD Testing Pipeline

Every pull request and build artifact must pass four automated verification gates before deployment:

```
+-----------------------------------------------------------------------------------+
|                            CI/CD VERIFICATION GATES                               |
+-------------------+-------------------+--------------------+----------------------+
| Gate 1: Static    | Gate 2: axe-core  | Gate 3: Lighthouse | Gate 4: Synthetic    |
| & Lint (ESLint    | Automated a11y    | CI (a11y >= 95,    | Performance & LCP    |
| jsx-a11y)         | (Pa11y-CI)        | Perf >= 90)        | Playwright Audit     |
+-------------------+-------------------+--------------------+----------------------+
```

### 7.2 Gate Definitions & Pass/Fail Thresholds

| Gate Name | Tool / Engine | Pass Criteria | Hard Failure Action |
|---|---|---|---|
| **Static a11y Lint** | `eslint-plugin-jsx-a11y` | 0 errors, 0 warnings | Block pull request check |
| **Automated axe Audit** | `@axe-core/cli` / `pa11y-ci` | 0 critical, 0 serious violations | Terminate build pipeline |
| **Lighthouse Accessibility** | Lighthouse CI (`@lhci/cli`) | Score **>= 95 / 100** | Reject deployment artifact |
| **Lighthouse Performance** | Lighthouse CI (`@lhci/cli`) | Score **>= 90 / 100** (Throttled) | Reject deployment artifact |
| **Core Web Vitals - LCP** | Chrome DevTools Trace / Lighthouse | LCP **< 2500ms** | Reject deployment artifact |
| **Core Web Vitals - INP** | Synthetic Event Timing API | Max INP **< 200ms** | Reject deployment artifact |
| **Core Web Vitals - CLS** | Layout Instability API | CLS **< 0.1** | Reject deployment artifact |
| **Tap Target Minimum Size** | DevTools Snapshot / axe-core | 100% elements >= 48x48px | Reject deployment artifact |
| **Color Contrast Verification** | axe-core `color-contrast` rule | 100% text passes WCAG AA | Reject deployment artifact |

### 7.3 Executable Verification Scripts

#### 1. Pa11y CI Configuration (`.pa11yci.json`)
```json
{
  "defaults": {
    "standard": "WCAG2AA",
    "runners": ["axe", "htmlcs"],
    "level": "error",
    "timeout": 30000,
    "viewport": {
      "width": 1280,
      "height": 800
    },
    "chromeLaunchConfig": {
      "args": ["--no-sandbox", "--disable-setuid-sandbox"]
    }
  },
  "urls": [
    "http://localhost:8000/",
    "http://localhost:8000/dashboard",
    "http://localhost:8000/settings"
  ]
}
```

#### 2. Lighthouse CI Configuration (`lighthouserc.json`)
```json
{
  "ci": {
    "collect": {
      "numberOfRuns": 3,
      "startServerCommand": "npm run start:preview",
      "url": ["http://localhost:8000/"],
      "settings": {
        "throttlingMethod": "simulate",
        "throttling": {
          "rttMs": 150,
          "throughputKbps": 1638.4,
          "cpuSlowdownMultiplier": 4
        },
        "formFactor": "mobile",
        "screenEmulation": {
          "mobile": true,
          "width": 390,
          "height": 844,
          "deviceScaleFactor": 3
        }
      }
    },
    "assert": {
      "assertions": {
        "categories:accessibility": ["error", {"minScore": 0.95}],
        "categories:performance": ["error", {"minScore": 0.90}],
        "largest-contentful-paint": ["error", {"maxNumericValue": 2500}],
        "cumulative-layout-shift": ["error", {"maxNumericValue": 0.1}],
        "color-contrast": "error",
        "tap-targets": "error",
        "document-title": "error",
        "html-has-lang": "error"
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    }
  }
}
```

#### 3. Playwright Synthetic LCP & a11y Gate Script (`tests/audit-gates.spec.ts`)
```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Automated Frontend Quality Gates', () => {
  test('A11Y Gate: Zero critical/serious WCAG AA violations', async ({ page }) => {
    await page.goto('http://localhost:8000/');
    await page.waitForLoadState('networkidle');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'section508'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Performance Gate: LCP < 2.5s and Tap Targets >= 48px', async ({ page }) => {
    await page.goto('http://localhost:8000/');

    // Measure LCP using PerformanceObserver
    const lcpTiming = await page.evaluate(async () => {
      return await new Promise<number>((resolve) => {
        let lcp = 0;
        new PerformanceObserver((entryList) => {
          const entries = entryList.getEntries();
          const lastEntry = entries[entries.length - 1];
          lcp = lastEntry.startTime;
          resolve(lcp);
        }).observe({ type: 'largest-contentful-paint', buffered: true });

        // Fallback timeout
        setTimeout(() => resolve(lcp), 3000);
      });
    });

    expect(lcpTiming).toBeLessThan(2500);

    // Verify all primary buttons meet 48x48px touch target
    const buttons = await page.locator('button, a[role="button"]').all();
    for (const btn of buttons) {
      const box = await btn.boundingBox();
      if (box && (await btn.isVisible())) {
        expect(box.width).toBeGreaterThanOrEqual(48);
        expect(box.height).toBeGreaterThanOrEqual(48);
      }
    }
  });
});
```

---

## 8. Regression Prevention & Governance Protocol

1. **Zero-Tolerance Defect Policy**: Any pull request triggering an axe-core violation or reducing Lighthouse accessibility below 95 or performance below 90 is automatically blocked from merge.
2. **Pre-Commit Hooks**: Husky hooks must run `npm run lint:a11y` locally before commits are accepted.
3. **Continuous Real User Monitoring (RUM)**: In production environments, client apps must embed the `web-vitals` attribution library to beacon live INP, LCP, and CLS percentiles back to backend analytics (`/analytics/vitals`). Any p75 regression triggers an automated incident alert.
