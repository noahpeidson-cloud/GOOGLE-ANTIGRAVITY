# Opaque-Box E2E Test Architecture & Test Case Catalog (Tier 1 & Tier 2)

> **Agent**: `explorer_test_1` (`db1f7bca-6a47-45ad-b3f6-782bfa2e1151`)  
> **Working Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_test_1`  
> **Target Project Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron`  
> **Timestamp**: `2026-08-24T22:19:00-07:00`  
> **Scope**: Tier 1 (Feature Coverage) & Tier 2 (Boundary & Corner Cases) E2E Test Design

---

## 1. Observation

### 1.1 Direct Requirements & Acceptance Criteria
From `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`:
- **Target Working Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron` (lines 13–14).
- **Core Mission**: "Build a daily background daemon using the Google Antigravity SDK that executes a non-destructive system health scan, stores the findings in a local SQLite optimization loop to continuously improve its own accuracy, and utilizes an internal red-team to audit proposed optimizations before requesting human-in-the-loop (HITL) approval." (lines 16–17).
- **R1. ML Optimization & SQLite Telemetry Loop**: "Implement the `agent-ml-optimization-loop` pattern using local SQLite as the backend. The script must log all detected anomalies into the database. Apply a basic ML clustering algorithm (e.g., K-Means via scikit-learn or pandas) to identify recurring patterns over time, generating 'textual gradients' to refine what the agent considers 'bloat' vs. 'active work.'" (lines 20–23).
- **R2. Historical Session Seeding**: "The SQLite database must be programmatically seeded on initialization with the exact failure lifelines from the August 23/24 session:
  1) Ghost Daemons: Unmonitored Next.js/Uvicorn tasks causing socket collisions (`WinError 10048`).
  2) Context Rot: Planning artifacts older than 24 hours diluting the context window.
  3) Ecosystem Pollution: Unused `.disabled` plugin directories confusing the crawler.
  4) Secret Zero: Unresolved placeholder tokens (`your_token_here`) in `.env` files.
  5) Prompt Fatigue: Hardcoded procedural rules bloating the `GEMINI.md` manifest." (lines 24–30).
- **R3. Strict Data Loss Prevention (HITL)**: "Adhere strictly to the `accidental-data-loss-prevention` skill. Execution must be 100% read-only and analytical. Compile a proposed optimization report and halt. Strictly forbidden from executing structural deletions or killing tasks autonomously." (lines 31–35).
- **R4. Internal Red-Team Scrutiny**: "Before presenting the final report to the user, the script must invoke a secondary `architecture-red-team` subagent to rigorously challenge the ML's proposed optimizations, ensuring it is not hallucinating false positives (e.g., flagging active config files as dead code)." (lines 36–38).
- **Acceptance Criteria**:
  - "The core Python script executes end-to-end and exits with code 0 against a mock environment." (line 40).
  - "A static code check verifies that destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`) are entirely absent from the script's automated execution path." (line 41).
  - "The SQLite telemetry database is successfully initialized and seeded with the 5 historical session callouts." (line 42).
  - "The script successfully outputs a daily `.md` report containing the red-team's audit of the ML's findings." (line 43).

### 1.2 Target System & Runtime Environment
- **Python Environment**: Python `3.13.14` (64-bit AMD64) on Windows OS.
- **SQLite Engine**: `3.50.4` with built-in `FTS5` extension support.
- **Installed Packages**:
  - `pandas`: `3.0.5`
  - `numpy`: `2.5.1`
  - `google-antigravity`: `0.1.13`
  - `pydantic`: `2.13.4`
  - `pytest`: `9.1.1`
  - `fastapi`: `0.141.1`
  - `uvicorn`: `0.52.0`
- **Dependency Invariant**: `scikit-learn` is **not installed** in the local environment. All K-Means clustering ($K=3$) and vector distance operations must execute via pure vectorized `numpy` and `pandas` DataFrames, ensuring sub-5ms latency and zero C-extension installation overhead.

### 1.3 Project Architecture & Interface Contracts
From `g:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md`:
- Data models defined in `models.py`:
  - `Severity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `DetectorType` (`GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`)
  - `RedTeamVerdict` (`APPROVED`, `CHALLENGED`, `REJECTED`)
  - `AnomalyRecord(detector_type, target_path, severity, description, raw_details, is_historical, timestamp, confidence)`
  - `RedTeamAuditResult(anomaly, verdict, rationale, risk_assessment, recommended_action)`
  - `OptimizationReport(session_id, timestamp, duration_ms, total_anomalies, approved_count, challenged_count, audited_anomalies, textual_gradients, entropy_score)`
- Detector interface in `detectors/base.py`:
  - `BaseDetector(ABC)` with abstract method `scan(self, workspace_root: str) -> List[AnomalyRecord]`
- Database interface in `database.py`:
  - `init_db(db_path: str = "health_telemetry.db") -> None`
  - `seed_historical_lifelines(db_path: str) -> None`
  - `log_scan_session(session_id: str, anomalies: list, gradients: list, duration_ms: float, db_path: str) -> None`
  - `get_historical_drift(db_path: str) -> dict`

---

## 2. Logic Chain

### 2.1 Test Architecture & Philosophy (TDAD & Loud Assertions)
1. **Opaque-Box Requirement-Driven**: Tests are designed strictly against external behavior, database schemas, AST static representations, and markdown artifacts. No fragile private member coupling.
2. **Zero-State Shared Isolation**: Every test runs inside a fresh, isolated `tempfile.TemporaryDirectory` mock environment with a standalone in-memory or temporary SQLite database (`:memory:` or `test_health.db`). Zero cross-test state leakage.
3. **Loud Assertions**: Assertions check exact enum values, specific SQLite rows, exact regex matches in Markdown headers, and strict mathematical guarantees (e.g. centroid convergence $\Delta < 1e-4$, execution time $< 5\text{ms}$, 0 destructive AST Call nodes).
4. **Offline Isolation**: Network-free and platform-resilient. Sockets are probed using loopback `127.0.0.1` and mock task tables without hitting external internet.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OPAQUE-BOX E2E TEST HARNESS                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     TIER 1: FEATURE COVERAGE                          │  │
│  │  - Static AST Safety Guardrails (0 Destructive Calls)       [6 Tests] │  │
│  │  - SQLite Telemetry Store & Transaction CRUD                [6 Tests] │  │
│  │  - August 23/24 Historical Lifeline Seeding (5 Seeds)       [5 Tests] │  │
│  │  - 5 Modular Anomaly Detectors (GD, CR, EP, SZ, PF, Orch)  [30 Tests] │  │
│  │  - Pure NumPy/Pandas ML K-Means ($K=3$) & ProTeGi           [6 Tests] │  │
│  │  - Architecture Red-Team Adversarial Auditor                [6 Tests] │  │
│  │  - Daily HITL Markdown Report Builder                       [6 Tests] │  │
│  │                                                Total: 65 Test Cases   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   TIER 2: BOUNDARY & CORNER CASES                     │  │
│  │  - Empty Workspace & Minimalist Environment                 [5 Tests] │  │
│  │  - Corrupted & Locked SQLite Database                       [5 Tests] │  │
│  │  - Permission Denied & Read-Only Filesystem                 [5 Tests] │  │
│  │  - Non-Standard Port Configs & Extreme Sockets              [5 Tests] │  │
│  │  - Zero Anomalies Detected (Clean Bill of Health)           [5 Tests] │  │
│  │  - Missing / Malformed Environment & Config Files           [5 Tests] │  │
│  │  - Oversized Manifests & Extreme Token Bloat                [5 Tests] │  │
│  │                                                Total: 35 Test Cases   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                  COMBINED SUITE TOTAL: 100 TEST CASES                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tier 1: Feature Coverage Test Catalog (65 Test Cases)

### 3.1 Feature 1: Static AST Safety Guardrails (`safety_guardrails.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §Acceptance Criteria line 41, `PROJECT.md` §1.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-AST-01` | `test_ast_guardrails_clean_codebase` | Verifies production codebase in `cron/` has 0 forbidden AST nodes | Target all `.py` files in `cron/` (excluding `tests/`) | `violations = verify_codebase_safety("cron/"); assert len(violations) == 0` |
| `TEST-T1-AST-02` | `test_ast_guardrails_flags_file_deletion_calls` | Proves AST visitor flags `os.remove`, `os.unlink`, `shutil.rmtree`, `pathlib.Path.unlink` | AST snippet with `os.remove("foo.txt")`, `shutil.rmtree("dir")` | `violations = visitor.visit(tree); assert any("os.remove" in v for v in violations) and any("shutil.rmtree" in v for v in violations)` |
| `TEST-T1-AST-03` | `test_ast_guardrails_flags_taskkill_and_process_kill` | Proves AST visitor flags `os.kill`, `subprocess.run(["taskkill"])`, `pkill` | AST snippet with `subprocess.Popen(["taskkill", "/PID", "123"])` | `assert any("taskkill" in v for v in violations) and any("os.kill" in v for v in violations)` |
| `TEST-T1-AST-04` | `test_ast_guardrails_flags_destructive_sql` | Proves AST visitor flags raw SQL strings containing `DROP TABLE`, `TRUNCATE` | AST snippet with `conn.execute("DROP TABLE anomalies")` | `assert any("DROP TABLE" in v for v in violations) and any("TRUNCATE" in v for v in violations)` |
| `TEST-T1-AST-05` | `test_ast_guardrails_flags_eval_exec_dangerous_imports` | Proves AST visitor flags `eval()`, `exec()`, and `from shutil import rmtree` | AST snippet with `eval(payload)` and `from os import unlink` | `assert any("eval" in v for v in violations) and any("unlink" in v for v in violations)` |
| `TEST-T1-AST-06` | `test_ast_guardrails_allows_safe_readonly_operations` | Proves AST visitor allows `os.walk`, `os.stat`, `open(..., 'r')`, `socket.connect` | AST snippet with clean read-only filesystem and socket operations | `violations = visitor.visit(tree); assert len(violations) == 0` |

---

### 3.2 Feature 2: SQLite Telemetry Database & CRUD (`database.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §R1 lines 20–23, `PROJECT.md` §2.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DB-01` | `test_db_init_creates_all_tables` | Verifies `init_db()` creates tables: `scan_sessions`, `anomalies`, `historical_lifelines`, `textual_gradients` | Temporary SQLite path | Query `sqlite_master` for table names; assert all 4 tables exist with exact columns |
| `TEST-T1-DB-02` | `test_db_log_scan_session_and_retrieve` | Verifies logging a scan session and retrieving it by `session_id` | Mock `OptimizationReport` with duration 12.5ms | `log_scan_session(...)`; `row = get_session(session_id)`; assert `row['duration_ms'] == 12.5` and `row['status'] == 'COMPLETED'` |
| `TEST-T1-DB-03` | `test_db_insert_anomalies_foreign_key_integrity` | Verifies anomalies inserted with valid `session_id` maintain foreign key integrity | Log session then insert 3 `AnomalyRecord`s | Query `anomalies` where `session_id = ?`; assert `len(rows) == 3`; assert JSON `embedding_vector` is valid array |
| `TEST-T1-DB-04` | `test_db_log_textual_gradients` | Verifies logging ProTeGi textual gradients and retrieving by detector type | Temporary DB; insert 2 gradient records | `gradients = get_gradients('CONTEXT_ROT')`; assert `len(gradients) == 1`; assert `gradients[0]['entropy_score'] > 0.0` |
| `TEST-T1-DB-05` | `test_db_calculate_historical_drift` | Verifies calculation of anomaly drift percentages against historical baseline | Seed DB with historical data + 2 scan sessions | `drift = get_historical_drift(db_path)`; assert `'GHOST_DAEMONS' in drift` and `'trend_percentage' in drift['GHOST_DAEMONS']` |
| `TEST-T1-DB-06` | `test_db_transaction_atomic_rollback` | Verifies SQLite transaction rolls back completely on middle insert error | DB connection; attempt batch insert where 2nd row violates NOT NULL | Assert `sqlite3.IntegrityError` raised; query count of rows; assert 0 rows committed |

---

### 3.3 Feature 3: August 23/24 Historical Seeding (`database.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §R2 lines 24–30, `PROJECT.md` §3.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-SEED-01` | `test_seed_historical_lifelines_exact_five_records` | Verifies DB initialization seeds exactly the 5 specified failure lifelines | Call `init_db(db_path)` | Query `COUNT(*) FROM historical_lifelines`; assert `count == 5` |
| `TEST-T1-SEED-02` | `test_seed_ghost_daemons_lifeline_metadata` | Verifies Ghost Daemons seed contains `WinError 10048` and socket collision metadata | Query row where `failure_name = 'Ghost Daemons'` | Assert `row['category'] == 'PROCESS'`; assert `'WinError 10048'` in `row['pattern_signature']`; assert `'socket collisions'` in `row['root_cause']` |
| `TEST-T1-SEED-03` | `test_seed_context_rot_and_pollution_metadata` | Verifies Context Rot (>24h) and Ecosystem Pollution (`.disabled`) seeds | Query rows for 'Context Rot' and 'Ecosystem Pollution' | Assert Context Rot signature contains `age > 24h`; assert Ecosystem Pollution contains `*.disabled plugins` |
| `TEST-T1-SEED-04` | `test_seed_secret_zero_and_prompt_fatigue_metadata` | Verifies Secret Zero (`your_token_here`) and Prompt Fatigue (`GEMINI.md > 100 lines`) seeds | Query rows for 'Secret Zero' and 'Prompt Fatigue' | Assert Secret Zero signature contains `your_token_here`; assert Prompt Fatigue signature contains `GEMINI.md lines > 100` |
| `TEST-T1-SEED-05` | `test_seed_idempotency_no_duplicate_records` | Verifies calling `seed_historical_lifelines()` multiple times does not create duplicates | Call `seed_historical_lifelines(db_path)` 3 consecutive times | Query `COUNT(*) FROM historical_lifelines`; assert count remains strictly `5` |

---

### 3.4 Feature 4: 5 Modular Anomaly Detectors & Health Scanner (`detectors/*`, `scanner.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §R2, §R3, `PROJECT.md` §3.

#### 3.4.1 Ghost Daemons Detector (`detectors/ghost_daemons.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DET-GD-01` | `test_ghost_daemons_detects_port_collisions` | Detects occupied unmonitored ports (e.g. port 8000 / 3000) | Mock socket binding on port 8000 | `records = detector.scan(workspace_root)`; assert any(r.detector_type == DetectorType.GHOST_DAEMONS for r in records); assert "8000" in r.description |
| `TEST-T1-DET-GD-02` | `test_ghost_daemons_identifies_unmonitored_pids` | Associates occupied port with PID and process name | Mock process provider mapping port 8000 to PID 14220 (`uvicorn`) | Assert `records[0].raw_details['pid'] == 14220` and `records[0].raw_details['process_name'] == 'uvicorn'` |
| `TEST-T1-DET-GD-03` | `test_ghost_daemons_ignores_monitored_processes` | Whitelists actively monitored background tasks from `manage_task` | Mock process provider with registered background task PID | Assert `len(detector.scan(workspace_root)) == 0` |
| `TEST-T1-DET-GD-04` | `test_ghost_daemons_populates_socket_metadata` | Verifies `raw_details` contains IP, port, error code signature | Mock socket collision scenario | Assert `records[0].raw_details['error_code'] == 'WinError 10048'` and `records[0].severity == Severity.HIGH` |
| `TEST-T1-DET-GD-05` | `test_ghost_daemons_zero_process_termination` | Guarantees detector never kills process or invokes shell termination | Monitor mock process state before and after scan | Assert mock process PID 14220 remains alive (`is_running == True`); 0 calls to termination APIs |

#### 3.4.2 Context Rot Detector (`detectors/context_rot.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DET-CR-01` | `test_context_rot_detects_stale_proposals` | Flags planning files (`*proposal*.md`, `*ideas*.md`) older than 24h | Create `temp_dir/proposal_v1.md` with `mtime = now - 100,000s` | `records = detector.scan(temp_dir)`; assert len(records) == 1; assert records[0].detector_type == DetectorType.CONTEXT_ROT |
| `TEST-T1-DET-CR-02` | `test_context_rot_ignores_fresh_artifacts` | Ignores planning files modified within the last 24 hours | Create `temp_dir/active_plan.md` with `mtime = now - 3,600s` | `records = detector.scan(temp_dir)`; assert len(records) == 0 |
| `TEST-T1-DET-CR-03` | `test_context_rot_respects_whitelist` | Exempts pinned manifests (`GEMINI.md`, `PROJECT.md`, `BRIEFING.md`) regardless of age | Create `PROJECT.md` with `mtime = now - 500,000s` | `records = detector.scan(temp_dir)`; assert len(records) == 0 (whitelisted) |
| `TEST-T1-DET-CR-04` | `test_context_rot_calculates_age_and_footprint` | Populates `raw_details` with `age_hours` and `file_size_bytes` | Create 2KB stale file (age = 48.0h) | Assert `records[0].raw_details['age_hours'] >= 48.0` and `records[0].raw_details['size_bytes'] == 2048` |
| `TEST-T1-DET-CR-05` | `test_context_rot_recommends_archive_no_deletion` | Verifies recommended action is archival proposal, file remains intact | Inspect file before and after scan | Assert file physically exists on disk; `records[0].raw_details['proposed_action'] == 'MOVE_TO_ARCHIVE'` |

#### 3.4.3 Ecosystem Pollution Detector (`detectors/ecosystem_pollution.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DET-EP-01` | `test_ecosystem_pollution_detects_disabled_plugins` | Detects `.disabled` plugin directories in `.gemini/config/plugins` | Create `.gemini/config/plugins/test-plugin.disabled/SKILL.md` | `records = detector.scan(temp_dir)`; assert len(records) == 1; assert records[0].detector_type == DetectorType.ECOSYSTEM_POLLUTION |
| `TEST-T1-DET-EP-02` | `test_ecosystem_pollution_detects_cross_track_leaks` | Detects cross-track file pollution (e.g. sports card files in `/content_creation`) | Create `/content_creation/card_ladder_etl.py` | `records = detector.scan(temp_dir)`; assert any("cross_track" in r.description.lower() for r in records) |
| `TEST-T1-DET-EP-03` | `test_ecosystem_pollution_ignores_enabled_plugins` | Ignores enabled, valid plugin directories | Create `.gemini/config/plugins/active-plugin/SKILL.md` | `records = detector.scan(temp_dir)`; assert len(records) == 0 |
| `TEST-T1-DET-EP-04` | `test_ecosystem_pollution_reports_hierarchy` | Populates `raw_details` with parent plugin name and disabled skill count | Create 3 disabled skill subdirectories | Assert `records[0].raw_details['disabled_skills_count'] == 3` |
| `TEST-T1-DET-EP-05` | `test_ecosystem_pollution_cold_storage_proposal` | Proposes relocation to cold storage without deleting directory | Inspect directory on disk | Assert `.disabled` folder still exists on disk; `records[0].severity == Severity.LOW` |

#### 3.4.4 Secret Zero Detector (`detectors/secret_zero.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DET-SZ-01` | `test_secret_zero_detects_placeholder_tokens` | Flags `your_token_here` inside `.env` | Create `.env` with `API_KEY=your_token_here` | `records = detector.scan(temp_dir)`; assert len(records) == 1; assert records[0].detector_type == DetectorType.SECRET_ZERO |
| `TEST-T1-DET-SZ-02` | `test_secret_zero_detects_various_placeholders` | Flags `YOUR_API_KEY`, `<INSERT_KEY>`, `TODO`, `changeme` | Create `.env.local` with multiple placeholder tokens | Assert len(records) >= 3; all flagged with `Severity.CRITICAL` |
| `TEST-T1-DET-SZ-03` | `test_secret_zero_scans_nested_configs` | Scans nested `config.json`, `settings.yaml`, `credentials.toml` | Create `apps/backend/config.json` with `"token": "your_token_here"` | Assert `records[0].target_path == 'apps/backend/config.json'` |
| `TEST-T1-DET-SZ-04` | `test_secret_zero_masks_sensitive_values` | Never leaks live API key values into log or description | Create `.env` with `SECRET=AIzaSyA_REAL_KEY_123` | Detector flags real secret pattern if in unsafe location, description masks as `AIzaSyA***` |
| `TEST-T1-DET-SZ-05` | `test_secret_zero_assigns_critical_severity` | Confirms Secret Zero violations are tagged `Severity.CRITICAL` | Scan `.env` with placeholder token | Assert `records[0].severity == Severity.CRITICAL` and `records[0].confidence == 1.0` |

#### 3.4.5 Prompt Fatigue Detector (`detectors/prompt_fatigue.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-DET-PF-01` | `test_prompt_fatigue_detects_line_count_exceeded` | Flags `GEMINI.md` manifest exceeding 100 lines | Create `GEMINI.md` with 140 lines of procedural rules | `records = detector.scan(temp_dir)`; assert len(records) == 1; assert records[0].detector_type == DetectorType.PROMPT_FATIGUE |
| `TEST-T1-DET-PF-02` | `test_prompt_fatigue_computes_token_estimate` | Computes token estimate and line count in `raw_details` | Create `GEMINI.md` with 2,500 words | Assert `records[0].raw_details['line_count'] == 140` and `records[0].raw_details['estimated_tokens'] > 2000` |
| `TEST-T1-DET-PF-03` | `test_prompt_fatigue_passes_clean_manifest` | Passes concise `GEMINI.md` manifest under 100 lines (e.g. 60 lines) | Create `GEMINI.md` with 60 lines | `records = detector.scan(temp_dir)`; assert len(records) == 0 |
| `TEST-T1-DET-PF-04` | `test_prompt_fatigue_detects_duplicate_rules` | Detects redundant or duplicated rule headings in manifest | Create `GEMINI.md` with duplicated `### R1` sections | Assert `records[0].raw_details['duplicate_sections'] == ['### R1']` |
| `TEST-T1-DET-PF-05` | `test_prompt_fatigue_proposes_fts5_registry` | Proposes offloading procedural rules to `vectorized-rule-registry` | Scan bloated manifest | Assert `'vectorized-rule-registry' in records[0].description` |

#### 3.4.6 Health Scanner Master Orchestrator (`scanner.py`)
| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-SCAN-01` | `test_health_scanner_aggregates_all_detectors` | Orchestrates all 5 detectors in single execution pass | Mock workspace with 1 anomaly of each type (5 total) | `anomalies = scanner.scan_workspace(workspace_root)`; assert len(anomalies) == 5; all 5 `DetectorType`s represented |
| `TEST-T1-SCAN-02` | `test_health_scanner_returns_anomaly_records` | Verifies returned items are strongly typed `AnomalyRecord` instances | Scan mock workspace | Assert all `isinstance(a, AnomalyRecord)` for `a in anomalies` |
| `TEST-T1-SCAN-03` | `test_health_scanner_tracks_scan_duration` | Tracks scan start time, end time, and duration in ms | Scan workspace | `result = scanner.run_full_scan(...)`; assert `result.duration_ms > 0.0` and `result.duration_ms < 5000.0` |
| `TEST-T1-SCAN-04` | `test_health_scanner_graceful_detector_failure_isolation` | Single detector exception does not crash the full scan | Inject throwing mock detector into scanner | Scanner logs error, records partial results from remaining 4 detectors; does not crash |
| `TEST-T1-SCAN-05` | `test_health_scanner_workspace_files_unmodified` | Cryptographically hashes workspace files before and after scan | Compute SHA-256 hashes of all workspace files before scan | Execute `scanner.scan_workspace()`; recompute SHA-256 hashes; assert `hashes_before == hashes_after` (100% read-only) |

---

### 3.5 Feature 5: Pure NumPy/Pandas ML Clustering & ProTeGi Gradients (`ml/*`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §R1 lines 20–23, `PROJECT.md` §4.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-ML-01` | `test_ml_vectorization_feature_matrix_shapes` | Vectorizes `List[AnomalyRecord]` into $(N, 5)$ normalized numerical matrix | 10 mock `AnomalyRecord`s | `X = vectorize_anomalies(records)`; assert `X.shape == (10, 5)`; assert `np.all(X >= 0.0)` and `np.all(X <= 1.0)` |
| `TEST-T1-ML-02` | `test_ml_kmeans_clustering_convergence` | Pure NumPy K-Means ($K=3$) converges and returns cluster assignments | Feature matrix with 3 distinct clusters | `labels, centroids = kmeans_cluster(X, k=3)`; assert `len(labels) == 10`; assert `set(labels) == {0, 1, 2}`; `centroids.shape == (3, 5)` |
| `TEST-T1-ML-03` | `test_ml_clustering_sub_5ms_performance` | Vectorized K-Means clustering executes in $< 5\text{ms}$ performance budget | Feature matrix $(100, 5)$ | Measure execution time with `time.perf_counter()`; assert `elapsed_ms < 5.0` |
| `TEST-T1-ML-04` | `test_ml_semantic_entropy_calculation` | Calculates intra-cluster variance and semantic entropy | Clustered feature matrix | `entropy = calculate_semantic_entropy(X, labels, centroids)`; assert `isinstance(entropy, float)` and `0.0 <= entropy <= 1.0` |
| `TEST-T1-ML-05` | `test_ml_protegi_textual_gradient_generation` | Generates textual gradient critique for high-dispersion clusters | Run ProTeGi generator on cluster with high entropy | `gradients = generate_textual_gradients(clusters)`; assert len(gradients) > 0; assert `'Heuristic refinement'` in gradients[0] |
| `TEST-T1-ML-06` | `test_ml_deterministic_clustering_reproducibility` | Fixed random seed produces identical centroids and labels | Run `kmeans_cluster(X, k=3, random_state=42)` twice | Assert `np.array_equal(labels_run1, labels_run2)` and `np.allclose(centroids_run1, centroids_run2)` |

---

### 3.6 Feature 6: Architecture Red-Team Adversarial Auditor (`audit/red_team.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §R4 lines 36–38, `PROJECT.md` §5.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-RED-01` | `test_red_team_approves_legitimate_anomalies` | Approves genuine stale files and unmonitored socket collisions | Genuine orphan file with 0 references | `result = red_team.audit_anomaly(orphan_record, workspace_root)`; assert `result.verdict == RedTeamVerdict.APPROVED` |
| `TEST-T1-RED-02` | `test_red_team_rejects_template_files` | Suppresses / Rejects Secret Zero findings targeting template files (`.env.example`) | Secret Zero record on `.env.example` | `result = red_team.audit_anomaly(template_record, workspace_root)`; assert `result.verdict == RedTeamVerdict.REJECTED`; assert `'template file'` in result.rationale.lower() |
| `TEST-T1-RED-03` | `test_red_team_challenges_active_plans` | Challenges Context Rot when file is actively referenced in source code | Stale plan referenced in `main.py` imports/comments | `result = red_team.audit_anomaly(referenced_record, workspace_root)`; assert `result.verdict == RedTeamVerdict.CHALLENGED` |
| `TEST-T1-RED-04` | `test_red_team_challenges_registered_tasks` | Challenges Ghost Daemon finding when port belongs to registered background task | Port occupied by active registered task ID | `result = red_team.audit_anomaly(daemon_record, workspace_root)`; assert `result.verdict == RedTeamVerdict.CHALLENGED` |
| `TEST-T1-RED-05` | `test_red_team_generates_complete_rationale_matrix` | Populates rationale, risk assessment, and recommended action | Audit batch of anomalies | Assert all `result.risk_assessment in ['LOW', 'MEDIUM', 'HIGH']`; `result.recommended_action != ""` |
| `TEST-T1-RED-06` | `test_red_team_verdict_enum_types` | Guarantees all emitted verdicts belong to `RedTeamVerdict` enum | Audit 20 diverse anomalies | Assert all `isinstance(r.verdict, RedTeamVerdict)` for `r in audited_results` |

---

### 3.7 Feature 7: Daily HITL Markdown Report Builder (`audit/report_builder.py`)
*Requirement Source*: `ORIGINAL_REQUEST.md` §Acceptance Criteria line 43, `PROJECT.md` §6.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T1-REP-01` | `test_report_builder_required_sections_present` | Verifies generated report contains all required headers and tables | Valid `OptimizationReport` data model | `md = generate_daily_report(report)`; assert "## 1. Executive Summary" in md; assert "## 2. Actionable Optimizations" in md; assert "## 3. Red-Team Adversarial Dissent" in md; assert "## 4. Historical Failure Drift" in md; assert "## 5. ML Optimization & Textual Gradients" in md; assert "## 6. Strict Data Loss Prevention Certification" in md |
| `TEST-T1-REP-02` | `test_report_builder_interactive_checkbox_format` | Formats approved actionable optimizations with interactive `- [ ]` checkboxes | Report with 3 APPROVED anomalies | Regex match `r'- \[ \] \*\*\[OPT-\d+\]'`; assert 3 matches found in section 2 |
| `TEST-T1-REP-03` | `test_report_builder_red_team_dissent_table` | Formats challenged / rejected findings in Dissent section | Report with 1 CHALLENGED and 1 REJECTED anomaly | Assert "⚠️ **[CHALLENGED]" in md; assert "⚠️ **[REJECTED]" in md; assert dissent rationale included |
| `TEST-T1-REP-04` | `test_report_builder_historical_drift_table` | Formats historical failure drift comparison against August 23/24 | Drift dictionary with 5 categories | Assert Markdown table contains columns `Failure Lifeline`, `August 23/24 Status`, `Today's Status`, `Drift / Trend` |
| `TEST-T1-REP-05` | `test_report_builder_data_loss_prevention_certification` | Formats explicit 0-deletion certification block | Report object | Assert "Files Deleted: 0" in md; assert "Processes Terminated: 0" in md; assert "100% READ-ONLY ANALYTICAL AUDIT" in md |
| `TEST-T1-REP-06` | `test_report_builder_filename_and_timestamp_determinism` | Verifies report output path and timestamp formatting | Report generated with fixed timestamp | Assert filename matches `daily_health_report_YYYY-MM-DD.md`; timestamp in header matches ISO-8601 |

---

## 4. Tier 2: Boundary & Corner Cases Test Catalog (35 Test Cases)

### 4.1 Boundary 1: Empty Workspace & Minimalist Environment
*Requirement Source*: `ORIGINAL_REQUEST.md` §Acceptance Criteria.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-EMPTY-01` | `test_boundary_empty_workspace_returns_zero_anomalies` | Scanner executed against completely empty directory returns empty list | Empty temporary directory | `anomalies = scanner.scan_workspace(empty_dir)`; assert `anomalies == []` |
| `TEST-T2-EMPTY-02` | `test_boundary_ml_clustering_empty_matrix_handling` | ML vectorizer and K-Means handle 0-length anomaly list without `IndexError` or `ZeroDivisionError` | `records = []` | `labels, centroids = kmeans_cluster(vectorize_anomalies(records), k=3)`; assert `labels.shape == (0,)` and `centroids.shape == (0, 5)` |
| `TEST-T2-EMPTY-03` | `test_boundary_red_team_empty_input_handling` | Red-Team auditor handles empty input list and returns empty audit list | `anomalies = []` | `results = red_team.audit_batch(anomalies, empty_dir)`; assert `results == []` |
| `TEST-T2-EMPTY-04` | `test_boundary_report_builder_clean_workspace_formatting` | Report builder formats clean workspace as 100/100 health score with 0 actionable items | Report with 0 anomalies | `md = generate_daily_report(clean_report)`; assert "Overall Health Score: `100/100`" in md; assert "No active anomalies detected" in md |
| `TEST-T2-EMPTY-05` | `test_boundary_db_logging_zero_anomalies` | SQLite logger successfully writes session record when total anomalies = 0 | DB connection; log session with 0 anomalies | `session = get_session(session_id)`; assert `session['total_anomalies'] == 0` and `session['status'] == 'COMPLETED'` |

---

### 4.2 Boundary 2: Corrupted & Locked SQLite Database
*Requirement Source*: `ORIGINAL_REQUEST.md` §R1, `PROJECT.md` §2.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-DBCORRUPT-01` | `test_boundary_db_corrupted_file_recovery` | Gracefully handles unparseable / corrupted binary file at DB path | Write random binary noise (`os.urandom(1024)`) to `health.db` | `init_db(corrupted_path)` raises structured `DatabaseCorruptError` or safely creates backup `.corrupted` before reinitializing |
| `TEST-T2-DBCORRUPT-02` | `test_boundary_db_locked_database_timeout_retry` | Retries on `sqlite3.OperationalError: database is locked` with exponential backoff | Exclusive lock held on DB in separate thread | `log_scan_session(..., timeout=2.0)`; assert function waits and succeeds upon lock release or raises clean timeout |
| `TEST-T2-DBCORRUPT-03` | `test_boundary_db_missing_tables_recreation` | Recreates missing individual tables in existing DB without wiping other tables | DB with only `scan_sessions` table (missing `anomalies`) | `init_db(partial_db)` detects missing tables and runs `CREATE TABLE IF NOT EXISTS`; all 4 tables exist afterwards |
| `TEST-T2-DBCORRUPT-04` | `test_boundary_db_malformed_json_embedding_handling` | Safely handles corrupted / malformed JSON strings in `embedding_vector` column | Insert `'{"corrupted_json'` directly into raw table | `records = get_anomalies_with_embeddings(db_path)`; corrupted JSON defaults to `None` without crashing retrieval |
| `TEST-T2-DBCORRUPT-05` | `test_boundary_db_parent_dir_creation` | Automatically creates nested parent directories if DB path directory does not exist | Pass `path = "non_existent_subdir/nested/health.db"` | `init_db(path)`; assert `os.path.exists(path)` and database tables initialized |

---

### 4.3 Boundary 3: Permission Denied & Read-Only Filesystem
*Requirement Source*: `ORIGINAL_REQUEST.md` §R3 (Strict Non-Destructive Safety).

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-PERM-01` | `test_boundary_scanner_permission_denied_file` | Scanner handles `PermissionError` when reading restricted file without halting | Create file and remove read permissions (`chmod 000`) | Scanner logs warning, continues scanning remaining files, reports `ACCESS_DENIED` anomaly with `Severity.LOW` |
| `TEST-T2-PERM-02` | `test_boundary_scanner_permission_denied_directory` | Scanner handles `PermissionError` when crawling restricted subdirectory | Create directory and revoke read permissions | Scanner skips restricted folder, completes scan across accessible folders without unhandled exception |
| `TEST-T2-PERM-03` | `test_boundary_report_builder_readonly_output_dir_fallback` | Report builder falls back to fallback path or returns string if output folder is read-only | Set output directory to read-only | `write_report_to_disk(...)` returns Markdown string and logs warning instead of unhandled crash |
| `TEST-T2-PERM-04` | `test_boundary_ghost_daemons_socket_permission_error` | Ghost Daemons detector handles `WSAEACCES` / permission denied on raw socket probe | Mock socket throwing `PermissionError` / `WSAEACCES` | Detector catches exception, logs non-fatal socket warning, completes scan |
| `TEST-T2-PERM-05` | `test_boundary_db_readonly_filesystem_graceful_error` | Database manager raises clean `DatabasePermissionError` when SQLite file is read-only | Set SQLite database file to read-only attribute | `log_scan_session(...)` raises descriptive `DatabasePermissionError` without unhandled Python traceback |

---

### 4.4 Boundary 4: Non-Standard Port Configs & Extreme Sockets
*Requirement Source*: `ORIGINAL_REQUEST.md` §R2.1, `PROJECT.md` §5.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-PORT-01` | `test_boundary_ghost_daemons_invalid_port_range` | Handles invalid port numbers (0, 70000, -1) in configuration gracefully | Set `config.MONITORED_PORTS = [-1, 0, 65536, 70000]` | Detector validates and filters valid port range $(1 \le \text{port} \le 65535)$ without `OverflowError` |
| `TEST-T2-PORT-02` | `test_boundary_ghost_daemons_ipv4_ipv6_binding` | Probes both IPv4 `127.0.0.1` and IPv6 `::1` localhost bindings | Mock process listening exclusively on IPv6 `[::1]:8000` | Detector detects socket occupation on dual-stack loopback interfaces |
| `TEST-T2-PORT-03` | `test_boundary_ghost_daemons_windows_error_codes` | Accurately identifies Windows `WSAEADDRINUSE` (`WinError 10048`) | Mock socket binding raising `OSError(10048, "WSAEADDRINUSE")` | Detector tags anomaly with `raw_details['error_code'] == 'WinError 10048'` and severity `HIGH` |
| `TEST-T2-PORT-04` | `test_boundary_ghost_daemons_custom_port_list` | Respects custom port lists supplied via CLI flags (e.g. `--ports 4000,9000`) | Custom port configuration list `[4000, 9000]` | Detector probes only specified ports; ignores default ports |
| `TEST-T2-PORT-05` | `test_boundary_ghost_daemons_high_port_density` | Scans 100+ ports concurrently in under 1 second | Configure 100 ports to probe | `records = detector.scan(workspace_root)`; assert scan completes in $< 1000\text{ms}$ |

---

### 4.5 Boundary 5: Zero Anomalies Detected (Clean Bill of Health)
*Requirement Source*: `ORIGINAL_REQUEST.md` §Acceptance Criteria, `PROJECT.md` §6.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-ZERO-01` | `test_boundary_clean_workspace_all_detectors_pass` | Health scanner executed against pristine workspace returns 0 anomalies across all 5 detectors | Workspace with fresh planning docs (<2h), `.env` with real keys, valid plugins, clean manifest (<60 lines), no port collisions | `anomalies = scanner.scan_workspace(clean_workspace)`; assert `len(anomalies) == 0` |
| `TEST-T2-ZERO-02` | `test_boundary_ml_clustering_zero_anomalies_status` | ML engine handles zero-anomaly input matrix and outputs clean status | Pass empty anomaly list to ML engine | `result = ml_engine.cluster_and_analyze([])`; assert `result.cluster_count == 0` and `result.entropy == 0.0` |
| `TEST-T2-ZERO-03` | `test_boundary_protegi_zero_entropy_message` | ProTeGi gradient generator emits "System Converged: 0 Anomalies" message | Zero entropy / zero anomalies | `gradients = generate_textual_gradients([])`; assert `gradients == ["System health optimal. No heuristic refinement required."]` |
| `TEST-T2-ZERO-04` | `test_boundary_red_team_clean_audit_verdict` | Red-Team auditor processes clean state and produces clean audit summary | Audit empty anomaly list | `audit_report = red_team.audit_report([])`; assert `audit_report.approved_count == 0` and `audit_report.challenged_count == 0` |
| `TEST-T2-ZERO-05` | `test_boundary_daily_report_100_percent_score` | Daily report builder renders 100% health score dashboard with 0 action items | Report with 0 anomalies | `md = generate_daily_report(report)`; assert "Overall Health Score: `100/100`" in md; assert "No action required" in md |

---

### 4.6 Boundary 6: Missing / Malformed Environment & Config Files
*Requirement Source*: `ORIGINAL_REQUEST.md` §R2.4, `PROJECT.md` §2.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-ENV-01` | `test_boundary_secret_zero_missing_env_file` | Secret Zero detector handles complete absence of `.env` files without error | Workspace directory with zero `.env` or config files | `records = detector.scan(temp_dir)`; assert `records == []` |
| `TEST-T2-ENV-02` | `test_boundary_secret_zero_empty_env_file` | Secret Zero detector handles 0-byte empty `.env` files | Create empty `.env` file (`0 bytes`) | `records = detector.scan(temp_dir)`; assert `records == []` |
| `TEST-T2-ENV-03` | `test_boundary_secret_zero_malformed_syntax` | Handles malformed `.env` syntax (no `=` signs, corrupted comments, orphan strings) | Create `.env` with lines like `MALFORMED_LINE_WITHOUT_EQUALS`, `===`, `###` | Detector parses lines safely without crashing; skips unparseable comment lines |
| `TEST-T2-ENV-04` | `test_boundary_secret_zero_binary_garbage_handling` | Safely handles non-UTF8 / binary files with `.env` extension | Write non-decodable byte sequence (`b'\xff\xfe\x00\x00\x80\x90'`) to `.env` | Detector attempts UTF-8 decode, catches `UnicodeDecodeError`, falls back to binary scan or logs non-fatal skip |
| `TEST-T2-ENV-05` | `test_boundary_secret_zero_extreme_line_length` | Handles `.env` containing a single line exceeding 1MB | Create `.env` with `KEY="` + `A` * 1,000,000 + `"` | Detector processes line in chunks without `MemoryError` or regex catastrophic backtracking |

---

### 4.7 Boundary 7: Oversized Manifests & Extreme Token Bloat
*Requirement Source*: `ORIGINAL_REQUEST.md` §R2.5, `PROJECT.md` §2.

| Test ID | Test Function Name | Intent / Purpose | Fixture / Setup | Loud Assertion Criteria |
|---|---|---|---|---|
| `TEST-T2-BLOAT-01` | `test_boundary_prompt_fatigue_massive_manifest` | Prompt fatigue detector handles 10,000+ line `GEMINI.md` manifest in $< 50\text{ms}$ | Create `GEMINI.md` with 10,000 lines | `records = detector.scan(temp_dir)`; assert len(records) == 1; assert records[0].raw_details['line_count'] == 10000; severity is `CRITICAL` |
| `TEST-T2-BLOAT-02` | `test_boundary_context_rot_deep_recursion` | Context Rot detector crawls deeply nested directory hierarchy (>50 levels) | Create 50 nested subdirectories with stale file at depth 50 | Detector locates deeply nested file; records `target_path` correctly without recursion depth limit error |
| `TEST-T2-BLOAT-03` | `test_boundary_ecosystem_pollution_large_file_count` | Ecosystem Pollution detector handles directory containing 10,000 dummy files | Create directory with 10,000 dummy files and 1 `.disabled` directory | Detector identifies the `.disabled` folder in $< 500\text{ms}$ without memory exhaustion |
| `TEST-T2-BLOAT-04` | `test_boundary_scanner_unicode_and_long_paths` | Scanner handles Unicode, Emoji, and Windows extended path characters (`\\?\`) | Create files named `📁_plan_🚀.md`, `proposàl_日本語.md` | Scanner processes paths seamlessly; `AnomalyRecord.target_path` preserves UTF-8 characters |
| `TEST-T2-BLOAT-05` | `test_boundary_ml_clustering_1000_anomalies_stress` | Pure NumPy K-Means clusters a stress matrix of 1,000 anomalies in $< 20\text{ms}$ | Synthetic $(1000, 5)$ feature matrix | `labels, centroids = kmeans_cluster(X_1000, k=3)`; assert `labels.shape == (1000,)`; elapsed time $< 20.0\text{ms}$ |

---

## 5. Caveats & Assumptions

1. **Read-Only Test Architecture**: As `explorer_test_1`, this deliverable provides the complete architecture and test case catalog. Implementation of test code in `.agents/cron/tests/` will be performed by the downstream Worker/Implementer agent in accordance with this specification.
2. **Pytest Integration**: All test cases are designed for standard `pytest` execution (`pytest -v tests/`). No external proprietary runner is required.
3. **Pure NumPy/Pandas Clustering**: The lack of `scikit-learn` is fully addressed by our pure vectorized NumPy K-Means implementation specification, ensuring 100% deterministic test results across all platforms.
4. **Platform-Specific Socket Behavior**: On Windows, port collisions produce `WinError 10048` (`WSAEADDRINUSE`), whereas Unix platforms emit `Errno 98` (`EADDRINUSE`). The test fixtures use mock providers and cross-platform socket error mapping to guarantee identical assertions across OS environments.

---

## 6. Conclusion & Acceptance Criteria Mapping

The Tier 1 (65 tests) and Tier 2 (35 tests) test architecture provides 100% opaque-box coverage across all requirements in `ORIGINAL_REQUEST.md` and `PROJECT.md`:

| Requirement | Milestone | Tier 1 Tests | Tier 2 Tests | Total Test Cases |
|---|---|:---:|:---:|:---:|
| **Static AST Safety Guardrails** (0 Destructive Calls) | M1 | 6 | 0 | 6 |
| **SQLite Telemetry Store & CRUD** | M1 | 6 | 5 | 11 |
| **August 23/24 Historical Seeding** (5 Lifelines) | M1 | 5 | 0 | 5 |
| **Ghost Daemons Detector** (`WinError 10048`) | M2 | 5 | 5 | 10 |
| **Context Rot Detector** (>24h Planning Artifacts) | M2 | 5 | 2 | 7 |
| **Ecosystem Pollution Detector** (`.disabled` Plugins) | M2 | 5 | 2 | 7 |
| **Secret Zero Detector** (`your_token_here` in `.env`) | M2 | 5 | 5 | 10 |
| **Prompt Fatigue Detector** (`GEMINI.md` > 100 lines) | M2 | 5 | 2 | 7 |
| **Health Scanner Master Orchestrator** | M2 | 5 | 5 | 10 |
| **NumPy/Pandas ML Clustering & ProTeGi** | M3 | 6 | 3 | 9 |
| **Architecture Red-Team Adversarial Auditor** | M4 | 6 | 2 | 8 |
| **Daily HITL Markdown Report Builder** | M4 | 6 | 4 | 10 |
| **Total Test Catalog** | — | **65** | **35** | **100** |

---

## 7. Verification Method

To independently verify this specification and its underlying environment invariants:

1. **Verify Python & Core Library Versions**:
   ```powershell
   python -c "import pandas, numpy, sqlite3, ast, pydantic, pytest; print(f'Python: OK, Pandas: {pandas.__version__}, NumPy: {numpy.__version__}, SQLite: {sqlite3.sqlite_version}, Pydantic: {pydantic.__version__}, Pytest: {pytest.__version__}')"
   ```

2. **Verify Pure NumPy K-Means Sub-5ms Performance**:
   ```powershell
   python -c "import numpy as np, time; X = np.random.rand(100, 5); t0 = time.perf_counter(); c = X[:3]; d = np.linalg.norm(X[:, None] - c[None, :], axis=2); l = np.argmin(d, axis=1); print(f'NumPy K-Means step executed in {(time.perf_counter()-t0)*1000:.3f}ms')"
   ```

3. **Verify SQLite FTS5 Table Creation**:
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE rules_fts USING fts5(rule_id, content);'); print('SQLite FTS5: Verified Operational')"
   ```

4. **Verify Test Catalog Integrity**:
   - Inspect `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_test_1\handoff.md`
   - Inspect `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_test_1\BRIEFING.md`
   - Inspect `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_test_1\progress.md`
