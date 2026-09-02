# Context — Milestone 3 EDM Content Strategy

## Goal
Upgrade the V2 EDM Content Strategy architecture in `content_creation/`:
1. R1: Librosa Drop Detection — automated 30s RMS peak window detection with CLI override support.
2. R2: YouTube Data API Auditing Loop (`youtube_publisher.py`) — unlisted upload, poll Content ID blocks, transition to public.
3. R3: Orchestrator Integration & Blueprint update — CLI flags in `orchestrator.py`, update `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` (Phases 3 & 4).
4. Testing: Unit, integration, mocks, and E2E verification.

## Key Directory Anchor
- Primary workspace: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`
- Authoritative requirements: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`
- Orchestrator metadata: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_4`

## Core Boundaries
- Adhere to `content_creation/GEMINI.md`.
- No sports card schemas.
- Do not hardcode test results.
- Full verification via automated test suites.
