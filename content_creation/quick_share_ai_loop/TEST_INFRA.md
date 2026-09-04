# E2E Test Infra: Quick Share AI Loop PostgreSQL Migration

## Test Philosophy
- Deterministic, requirement-driven testing with **Loud Assertions** (zero shared state, explicit failure modes).
- Adheres to Rule **R2** (The Zero-Discretion Mandate / The Leash Protocol) and Rule **R26** (The Background Daemon Auth Guardrail).
- Mocking and test harness simulate Cloud SQL PostgreSQL behavior, connection pool exhaustion, idle socket disconnects, and JSONB upserts without external live DB dependency.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|-------------|:-----------------:|:-----------------:|:----------------------:|:-------------------:|
| 1 | Rule R26 Auth Validation | R3 | 5 tests | 5 tests | ✓ | ✓ |
| 2 | PostgreSQL & Data Connect Schemas | R2 | 5 tests | 5 tests | ✓ | ✓ |
| 3 | Threaded Connection Pool Management | R1, R4 | 5 tests | 5 tests | ✓ | ✓ |
| 4 | Safe Context Manager Checkout | R1, R4 | 5 tests | 5 tests | ✓ | ✓ |
| 5 | JSONB 4K Video Tag Upsert | R1, R2 | 5 tests | 5 tests | ✓ | ✓ |

## Test Architecture
- **Runner**: `pytest -v` (and `python -m unittest tests/test_database_sink.py`)
- **Location**: `tests/test_database_sink.py`, `tests/conftest.py`
- **Pass/Fail Semantics**: All test suites must return exit code 0 with 0 assertions failed.

## Test Tiers
1. **Tier 1 - Feature Coverage**:
   - `test_get_db_config_success`: Validates correct parsing of valid `.env` variables.
   - `test_get_db_config_missing_vars`: Validates loud `ValueError` when required env vars are missing.
   - `test_init_db_executes_ddl`: Validates table and index creation statements.
   - `test_insert_video_analytics_basic`: Validates standard insert with dict payload.
   - `test_close_pool_terminates_connections`: Validates clean shutdown.
2. **Tier 2 - Boundary & Corner Cases**:
   - Empty/whitespace `PG_PORT` default fallback (5432) vs invalid non-numeric port rejection.
   - None/empty `viral_features` (defaults to `[]`::jsonb).
   - None/empty `technical` metrics (defaults to `{}`::jsonb).
   - Backslash and special characters in Windows file paths.
   - Upsert with duplicate `filename` (triggering `ON CONFLICT DO UPDATE`).
3. **Tier 3 - Cross-Feature Combinations**:
   - Stringified JSON vs Python Dict payload inputs.
   - Concurrency & Threaded Checkout across multiple simultaneous threads.
   - Transaction Rollback on SQL Execution Error without polluting connection state.
4. **Tier 4 - Real-World Application Workloads**:
   - Full 4K 60fps video taxonomy payload insertion (`EDM`, `Sports Cards`, `Travel`).
   - Mock Watchdog Event Pipeline Simulation (File Ingestion -> AI Tagging -> DB Sink -> Copier).
5. **Tier 5 - Adversarial & Red Team Hardening**:
   - Simulated Cloud SQL 10-minute idle disconnect (`OperationalError`) -> Pre-ping recovery.
   - Pool Starvation Stress Test (attempting 20 concurrent checkouts on pool of size 10).
   - Exception during cursor execution guarantees connection returned to pool (`putconn`).

## Coverage Thresholds
- Tier 1: ≥5 test cases per feature
- Tier 2: ≥5 boundary test cases
- Tier 3: Pairwise coverage of error and concurrency states
- Tier 4: Real-world 4K video payload scenarios
- Tier 5: Red Team connection leak stress tests
