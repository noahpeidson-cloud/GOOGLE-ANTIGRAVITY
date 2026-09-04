# Project Plan: Viral Trend Pipeline Python Integration Test Suite

## Objective
Build a complete, standalone Python integration test suite using pytest to validate the Viral Trend Pipeline:
- **R1. Extraction Mocking**: Chrome DevTools accessibility tree extraction mock fixtures (TikTok, YouTube tags) and Android CLI layout dump mock fixtures (Instagram UI trees).
- **R2. SQLite Mark-and-Sweep Validation**: Seeding trends.db across 30 days, asserting exact pre-sweep row counts, executing 14-day rolling window purge, asserting post-sweep row counts.
- **R3. BigQuery Payload Formatting**: Unnested tag array normalization, case preservation, deduplication, type casting, schema compatibility with AI.FORECAST and AI.KEY_DRIVERS.
- **Performance & Isolation**: Deterministic mock extractors (zero network calls), complete suite execution under 10 seconds.

## Milestones & Execution Stages
1. **Stage 0: Survey & Codebase Investigation**
   - Explorer 1 (Codebase & Environment Explorer): Investigate available Python tools, pytest configuration, project layout, virtual environments, dependencies.
   - Explorer 2 / Spec Miner 1 (Viral Trend Pipeline Spec Miner): Deep-dive into viral-trend-pipeline specifications, schemas, SQLite mark-and-sweep logic, and BigQuery ML schema expectations.
   - Explorer 3 / Spec Miner 2 (Chrome DevTools & Android CLI Mocking Specialist): Map the exact mock interfaces, accessibility tree structures, and Android layout dump formats needed for deterministic fixtures.
2. **Stage 1: Architecture & Interface Specification**
   - Synthesize survey findings into `PROJECT.md` with complete Feature Inventory and Interface Contracts.
3. **Stage 2: Milestone Implementation (Dual Track & Iteration Loops)**
   - M1: Test harness setup, directory layout, pytest plugins/fixtures, mock extractors for Chrome DevTools & Android CLI (R1).
   - M2: SQLite schema, mark-and-sweep GC logic implementation & validation tests (R2).
   - M3: BigQuery payload builder, schema normalizer, and validation tests (R3).
   - M4: Integration test runner and full test suite verification.
4. **Stage 3: Verification & Hardening**
   - Reviewers review all code and test suites.
   - Challengers execute adversarial stress testing and edge-case validation.
   - Forensic Auditor audits code for cheating, hardcoding, and integrity violations.
5. **Stage 4: Completion & Reporting**
   - Final review and handoff report back to Sentinel.
