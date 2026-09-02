## 2026-08-22T13:06:24Z

You are an expert Frontend Architect and Accessibility / Performance Specialist.

Your working directory is: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_web_a11y
The original request file is at: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md

Read ORIGINAL_REQUEST.md before starting.

Mission:
Formalize mandatory modern frontend engineering, accessibility (a11y), and web performance constraints and verification testing gates:
1. Modern Web Guidance & UI Architecture:
   - Component-driven design, responsive layouts, progressive enhancement, offline capabilities / PWA integration.
   - State management, resilient error boundaries, optimistic UI updates, secure client-side storage.
2. Strict Accessibility (a11y) Standards & Rules:
   - WCAG 2.1 Level AA & Section 508 compliance.
   - Semantic HTML5 structure (landmarks, headings, lists).
   - ARIA roles, states, and properties (aria-live, aria-expanded, aria-labelledby, etc.).
   - Comprehensive keyboard navigation (tab order, visible focus indicators, skip navigation links, trap focus in modals).
   - Minimum tap target sizes (48x48px with adequate spacing).
   - Strict color contrast ratios (minimum 4.5:1 for normal text, 3:1 for large text and UI components).
   - Screen reader announcement protocols.
3. Web Performance & Core Web Vitals Optimization:
   - Largest Contentful Paint (LCP) budget: Target < 2.5s (optimization of hero assets, fetchpriority="high", preconnect, CDN edge caching, critical CSS inlining, font-display: swap).
   - Interaction to Next Paint (INP) < 200ms, Cumulative Layout Shift (CLS) < 0.1.
   - Asset compression (AVIF, WebP), lazy loading of offscreen images/components, modern bundle splitting.
4. Mandatory CI/CD Verification & Testing Gates:
   - Automated a11y testing gates (axe-core, Lighthouse accessibility score >= 95, Pa11y).
   - Automated performance testing gates (Lighthouse Performance score >= 90, WebPageTest, synthetic LCP audit scripts).
   - Regression prevention protocols.

Deliverables:
- Write your comprehensive standards and testing gates specification to `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_web_a11y\web_a11y_performance_specs.md`.
- Write your formal handoff to `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_web_a11y\handoff.md`.
- Send a completion message back to the orchestrator referencing the report paths.
